import base64
from datetime import datetime
from pathlib import Path

import controlflow as cf
from prefect import flow, task
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.caching import INPUTS_MINUS_AGENTS
from app.settings import settings as root_settings
from app.storage import DiskStorage
from app.types import ObservationSummary
from assistant import run_agent_loop
from assistant.observers.gmail import GmailObserver, get_gmail_service
from assistant.utilities.loggers import get_logger

logger = get_logger('assistant.email')


class EmailSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='EMAIL_', extra='ignore')

    enabled: bool = Field(default=False, description='Enable email processing')
    credentials_path: Path = Field(default=Path(__file__).parent.parent / 'secrets' / 'gmail_credentials.json')
    token_path: Path = Field(default=Path(__file__).parent.parent / 'secrets' / 'gmail_token.json')
    check_interval_seconds: int = Field(default=300, ge=10)
    instructions_path: Path = Field(default=Path(__file__).parent.parent / 'email_instructions.md')

    @property
    def instructions(self) -> str:
        """Load instructions from Markdown file"""
        if not self.instructions_path.exists():
            return """
            Review these email messages and create a concise summary.
            Group related messages by thread and highlight urgent items.
            """
        return self.instructions_path.read_text()


email_settings = EmailSettings()


@root_settings.hl.instance.require_approval()
def send_email(recipient: str, subject: str, body: str) -> str | None:
    """Send an email using the Gmail API."""
    service = get_gmail_service(
        creds_path=email_settings.credentials_path,
        token_path=email_settings.token_path,
    )

    message = {'raw': base64.urlsafe_b64encode(f'To: {recipient}\nSubject: {subject}\n\n{body}'.encode()).decode()}

    try:
        service.users().messages().send(userId='me', body=message).execute()  # type: ignore
        return f'Email sent to {recipient}'
    except Exception as e:
        logger.error(f'Failed to send email: {e}')
        raise


@task(cache_policy=INPUTS_MINUS_AGENTS)
def process_gmail_observations(storage: DiskStorage, agents: list[cf.Agent]) -> ObservationSummary | None:
    """Process Gmail observations and create a summary"""

    events = []
    with GmailObserver(
        creds_path=email_settings.credentials_path,
        token_path=email_settings.token_path,
    ) as observer:
        if not (events_list := list(observer.observe())):
            logger.info('Successfully checked Gmail - no new messages found')
            return None

        # Create enriched events with AI analysis
        for event in events_list:
            events.append(
                {
                    'type': 'email',
                    'timestamp': datetime.now(root_settings.tz).isoformat(),
                    'hash': event.id,
                    'subject': event.subject,
                    'sender': event.sender,
                    'snippet': event.snippet,
                }
            )
            logger.info_kv(event.sender, event.subject)

        raw_summary = ObservationSummary(
            timestamp=datetime.now(root_settings.tz),
            summary='',  # Empty summary for raw storage
            events=events,
            source_types=['email'],
        )
        storage.store_raw(raw_summary)

        summary = ObservationSummary(
            timestamp=datetime.now(root_settings.tz),
            summary=run_agent_loop(
                'Create summary of new messages',
                agents=agents,
                instructions=email_settings.instructions,
                context={'events': events},
                result_type=str,
            ),
            events=events,
            source_types=['email'],
        )

        storage.store_processed(summary)
        logger.info(f'Finished processing {len(events)} new email(s)')
        return summary


@flow
def check_email(storage: DiskStorage, agents: list[cf.Agent]) -> None:
    """Process observations and store using storage abstraction"""
    logger.info_style('Checking Gmail for 📧')
    logger.debug(f'Processing emails with instructions: {email_settings.instructions}')
    process_gmail_observations(storage, agents)
