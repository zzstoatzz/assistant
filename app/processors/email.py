import base64
from datetime import UTC, datetime

import controlflow as cf
from prefect import flow, task

from app.settings import settings
from app.storage import DiskStorage
from app.types import ObservationSummary
from assistant.observers.gmail import GmailObserver, get_gmail_service
from assistant.utilities.loggers import get_logger

logger = get_logger('assistant.email')


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
def process_gmail_observations(storage: DiskStorage, agents: list[cf.Agent]) -> ObservationSummary | None:
    """Process Gmail observations and create a summary"""
    logger = get_logger()

    events = []
    with GmailObserver(
        creds_path=settings.email_credentials_dir / 'gmail_credentials.json',
        token_path=settings.email_credentials_dir / 'gmail_token.json',
    ) as observer:
        if not (events_list := list(observer.observe())):
            logger.info('Successfully checked Gmail - no new messages found')
            return None

        for event in events_list:
            events.append(
                {
                    'type': 'email',
                    'timestamp': datetime.now(UTC).isoformat(),
                    'subject': event.subject,
                    'sender': event.sender,
                    'snippet': event.snippet,
                }
            )
            logger.info_kv(event.sender, event.subject)

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

    return ObservationSummary(timestamp=datetime.now(UTC), summary=summary, events=events, source_types=['email'])


@flow
def check_email(storage: DiskStorage, agents: list[cf.Agent]) -> None:
    """Process observations and store using storage abstraction"""
    logger.info_style('Checking Gmail for 📧')
    if summary := process_gmail_observations(storage, agents):
        storage.store_raw(summary)
        storage.store_processed(summary)
