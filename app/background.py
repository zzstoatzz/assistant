import asyncio
from datetime import datetime
from typing import Any

import controlflow as cf
from prefect import flow, get_run_logger, task
from prefect.logging.loggers import get_logger
from pydantic import BaseModel

from app.settings import settings
from assistant.observers.gmail import GmailObserver

logger = get_logger()


class ObservationSummary(BaseModel):
    """Summary of observations from a time period"""

    timestamp: datetime
    summary: str
    events: list[dict[str, Any]]
    source_types: list[str]


# Create monitor agent for background processing
secretary = cf.Agent(
    name='Secretary',
    instructions="""
    You are an assistant that monitors various information streams like email and chat.
    Your role is to:
    1. Process incoming events
    2. Group related items
    3. Identify important or urgent matters
    4. Create clear, concise summaries
    """,
)


@task
def process_gmail_observations() -> ObservationSummary:
    """Process Gmail observations and create a summary"""
    logger = get_run_logger()

    events = []
    observer = GmailObserver(
        creds_path=settings.email_credentials_dir / 'gmail_credentials.json',
        token_path=settings.email_credentials_dir / 'gmail_token.json',
    )

    try:
        observer.connect()
        for event in observer.observe():
            events.append(
                e := {
                    'type': 'email',
                    'timestamp': datetime.now().isoformat(),
                    'subject': event.subject,
                    'sender': event.sender,
                    'snippet': event.snippet,
                }
            )
            logger.info(f'{e["sender"]}: {e["subject"]}')
    finally:
        observer.disconnect()

    if not events:
        return ObservationSummary(
            timestamp=datetime.now(), summary='No new messages', events=[], source_types=['email']
        )

    # Use the monitor agent to create a summary
    summary = cf.run(
        'Create summary of new messages',
        agents=[secretary],
        instructions="""
        Review these events and create a concise summary.
        Group related items and highlight anything urgent or important.
        """,
        context={'events': events},
        result_type=str,
    )

    return ObservationSummary(timestamp=datetime.now(), summary=summary, events=events, source_types=['email'])


@flow
def check_email() -> None:
    """Process observations and save summary to disk"""
    summary = process_gmail_observations()

    summary_path = settings.summaries_dir / f'summary_{summary.timestamp:%Y%m%d_%H%M%S}.json'
    summary_path.write_text(summary.model_dump_json(indent=2))


async def periodically_check_email():
    """Periodically check email in the background"""
    while True:
        try:
            check_email()
        except Exception as e:
            logger.error(f'Email check failed: {e}')
        await asyncio.sleep(settings.email_check_interval_seconds)
