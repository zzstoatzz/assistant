import base64
from datetime import datetime

import controlflow as cf
from prefect import flow, task
from prefect.logging import get_logger

from app.settings import settings
from app.types import ObservationSummary
from assistant.observers.gmail import GmailObserver, get_gmail_service

logger = get_logger()


@settings.hl.instance.require_approval()
def send_email(recipient: str, subject: str, body: str) -> str | None:
    """Send an email using the Gmail API."""
    service = get_gmail_service(
        creds_path=settings.email_credentials_dir / 'gmail_credentials.json',
        token_path=settings.email_credentials_dir / 'gmail_token.json',
    )

    message = {'raw': base64.urlsafe_b64encode(f'To: {recipient}\nSubject: {subject}\n\n{body}'.encode()).decode()}

    try:
        service.users().messages().send(userId='me', body=message).execute()  # type: ignore
        return f'Email sent to {recipient}'
    except Exception as e:
        logger.error(f'Failed to send email: {e}')
        raise


@task
def process_gmail_observations(agents: list[cf.Agent]) -> ObservationSummary | None:
    """Process Gmail observations and create a summary"""
    logger = get_logger()

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
        agents=agents,
        instructions="""
        Review these events and create a concise summary.
        Group related items and highlight anything urgent or important.
        """,
        context={'events': events},
        result_type=str,
    )

    return ObservationSummary(timestamp=datetime.now(), summary=summary, events=events, source_types=['email'])


@flow
def check_email(agents: list[cf.Agent]) -> None:
    """Process observations and save summary to disk"""
    if summary := process_gmail_observations(agents):
        summary_path = settings.summaries_dir / f'summary_{summary.timestamp:%Y%m%d_%H%M%S}.json'
        summary_path.write_text(summary.model_dump_json(indent=2))
