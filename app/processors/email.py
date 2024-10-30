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


# @settings.hl.instance.require_approval()
def send_email(recipient: str, subject: str, body: str) -> str | None:
    """Send an email using the Gmail API."""
    service = get_gmail_service(
        creds_path=settings.email_credentials_dir / 'gmail_credentials.json',
        token_path=settings.email_credentials_dir / 'gmail_token.json',
    )

    message = {'raw': base64.urlsafe_b64encode(f'To: {recipient}\nSubject: {subject}\n\n{body}'.encode()).decode()}

    # Show message details and get approval
    print('\nPreparing to send email:')
    print(f'To: {recipient}')
    print(f'Subject: {subject}')
    print(f'Body:\n{body}')

    if input('\nSend this email? (y/n): ').lower().strip() != 'y':
        logger.info('Email sending cancelled by user')
        return None

    try:
        service.users().messages().send(userId='me', body=message).execute()  # type: ignore
        return f'Email sent to {recipient}'
    except Exception as e:
        logger.error(f'Failed to send email: {e}')
        raise


@task
def process_gmail_observations(storage: DiskStorage, agents: list[cf.Agent]) -> ObservationSummary | None:
    """Process Gmail observations and create a summary"""

    events = []
    with GmailObserver(
        creds_path=settings.email_credentials_dir / 'gmail_credentials.json',
        token_path=settings.email_credentials_dir / 'gmail_token.json',
    ) as observer:
        if not (email_events := list(observer.observe())):
            logger.info('Successfully checked Gmail - no new messages found')
            return None

        # Create events from BaseEvent instances
        for event in email_events:
            events.append(
                {
                    'type': event.source_type,
                    'timestamp': event.timestamp.isoformat(),
                    'hash': event.hash,
                    **event.content,  # Includes subject, sender, snippet, thread_id
                }
            )
            logger.info_kv(event.content['sender'], event.content['subject'])

        # Store raw events immediately
        raw_summary = ObservationSummary(
            timestamp=datetime.now(UTC),
            summary='',
            events=events,
            source_types=['email'],
        )
        storage.store_raw(raw_summary)

    # Create processed summary with semantic grouping
    summary = ObservationSummary(
        timestamp=datetime.now(UTC),
        summary=cf.run(
            'Create summary of new messages',
            agents=agents,
            instructions="""
            Review these email messages and create a concise summary.
            Group related messages by:
            1. Thread/conversation
            2. Sender organization
            3. Topic similarity
            Highlight anything urgent or requiring immediate attention.
            """,
            context={'events': events},
            result_type=str,
        ),
        events=events,
        source_types=['email'],
    )

    storage.store_processed(summary)
    return summary


@flow
def check_email(storage: DiskStorage, agents: list[cf.Agent]) -> None:
    """Process observations and store using storage abstraction"""
    logger.info_style('Checking Gmail for 📧')
    process_gmail_observations(storage, agents)
