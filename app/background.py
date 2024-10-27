import asyncio
import base64
from collections.abc import Callable
from datetime import datetime
from typing import Any

import controlflow as cf
from humanlayer import HumanLayer, ContactChannel, SlackContactChannel
from prefect import flow, get_run_logger, task
from prefect.logging.loggers import get_logger
from pydantic import BaseModel

from app.settings import settings
from assistant.observers.gmail import GmailObserver, get_gmail_service

logger = get_logger()

hl = HumanLayer(
    contact_channel=ContactChannel(
        slack=SlackContactChannel(
            channel_or_user_id='',  # default to dm from app
            context_about_channel_or_user='a dm with nate',
            experimental_slack_blocks=True,  # pretty print slack approvals
        )
    )
)


@hl.require_approval()
def send_email(recipient: str, subject: str, body: str) -> None:
    """Send an email using the Gmail API."""
    service = get_gmail_service(
        creds_path=settings.email_credentials_dir / 'gmail_credentials.json',
        token_path=settings.email_credentials_dir / 'gmail_token.json',
    )

    message = {'raw': base64.urlsafe_b64encode(f'To: {recipient}\nSubject: {subject}\n\n{body}'.encode()).decode()}

    try:
        service.users().messages().send(userId='me', body=message).execute()
        return f'Email sent to {recipient}'
    except Exception as e:
        logger.error(f'Failed to send email: {e}')
        raise


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
    5. Reach out to the human if something is interesting or urgent
    6. Send messages on the human's behalf
    """,
    tools=[hl.human_as_tool(), send_email],
)


@task
def process_gmail_observations() -> ObservationSummary | None:
    """Process Gmail observations and create a summary"""
    logger = get_run_logger()

    events = []
    with GmailObserver(
        creds_path=settings.email_credentials_dir / 'gmail_credentials.json',
        token_path=settings.email_credentials_dir / 'gmail_token.json',
    ) as observer:
        # Get all events at once and break if none
        if not (events_list := list(observer.observe())):
            return None  # Return None instead of empty summary

        # Process events if we have them
        for event in events_list:
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
    if summary := process_gmail_observations():
        summary_path = settings.summaries_dir / f'summary_{summary.timestamp:%Y%m%d_%H%M%S}.json'
        summary_path.write_text(summary.model_dump_json(indent=2))


@flow
def check_observations() -> None:
    """Check observations on disk and process if necessary"""
    # Create processed directory if it doesn't exist
    processed_dir = settings.summaries_dir / 'processed'
    processed_dir.mkdir(exist_ok=True)

    # Only get unprocessed summaries
    summary_files = list(settings.summaries_dir.glob('*.json'))
    unprocessed_summaries = [
        p
        for p in summary_files
        if p.parent == settings.summaries_dir  # Exclude files in processed subdir
    ]

    if not unprocessed_summaries:
        return None

    summaries = [p.read_text() for p in unprocessed_summaries]

    maybe_interesting_stuff = cf.run(
        'Check if any of the summaries are interesting, reach out to the human if they are',
        agents=[secretary],
        context={'summaries': summaries},
    )

    # Move processed files to processed directory
    for file_path in unprocessed_summaries:
        new_path = processed_dir / file_path.name
        file_path.rename(new_path)
        logger.info(f'Moved processed summary: {file_path.name}')

    return maybe_interesting_stuff


async def run_periodic_task(
    task_func: Callable[[], Any], interval_seconds: float, task_name: str = 'periodic task'
) -> None:
    """
    Run a synchronous function periodically with proper cancellation handling.

    Args:
        task_func: The synchronous function to run periodically
        interval_seconds: Number of seconds to wait between runs
        task_name: Name of the task for logging purposes
    """
    logger.info(f'Starting {task_name} with {interval_seconds} second interval')
    while True:
        try:
            # Run the task in the executor to prevent blocking
            await asyncio.get_event_loop().run_in_executor(None, task_func)
        except Exception as e:
            logger.error(f'{task_name} failed: {e}')
        await asyncio.sleep(interval_seconds)


async def periodically_check_email():
    """Periodically check email in the background"""
    # Remove print statement and use logger instead
    logger.info(f'Starting email checker with interval: {settings.email_check_interval_seconds} seconds')
    await run_periodic_task(
        task_func=check_email, interval_seconds=settings.email_check_interval_seconds, task_name='email check'
    )


async def periodically_check_observations():
    """Periodically check observations on disk"""
    await run_periodic_task(
        task_func=check_observations,
        interval_seconds=settings.observation_check_interval_seconds,
        task_name='observation check',
    )
