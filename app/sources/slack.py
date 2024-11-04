from datetime import UTC, datetime
from pathlib import Path

import controlflow as cf
from prefect import flow, task
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from app.caching import INPUTS_MINUS_AGENTS
from app.settings import settings as root_settings
from app.storage import DiskStorage
from app.types import ObservationSummary
from assistant import run_agent_loop
from assistant.observers.slack import SlackObserver
from assistant.utilities.loggers import get_logger

logger = get_logger('assistant.slack')


class SlackSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='SLACK_', extra='ignore')

    enabled: bool = Field(default=False, description='Enable Slack processing')
    bot_token: str | None = Field(default=None, description='Slack bot token')
    check_interval_seconds: int = Field(default=300, ge=10)

    instructions_path: Path = Field(default=Path(__file__).parent.parent / 'slack_instructions.md')

    @property
    def instructions(self) -> str:
        """Load instructions from Markdown file"""
        if not self.instructions_path.exists():
            return """
            Review these Slack messages and create a concise summary.
            Group by channel and thread context, highlight important items.
            """
        return self.instructions_path.read_text()


slack_settings = SlackSettings()


@task(cache_policy=INPUTS_MINUS_AGENTS)
def process_slack_observations(storage: DiskStorage, agents: list[cf.Agent]) -> ObservationSummary | None:
    """Process Slack messages and create a summary"""
    if not (token := slack_settings.bot_token):
        logger.error('Slack bot token is not set')
        return None

    processed_hashes = set()
    for path_iter in [storage.get_processed(), storage.get_unprocessed()]:
        for path in path_iter:
            try:
                summary = ObservationSummary.model_validate_json(path.read_text())
                for event in summary.events:
                    if event.get('hash'):
                        processed_hashes.add(event['hash'])
            except Exception as e:
                logger.error(f'Error loading summary {path}: {e}')

    events = []
    with SlackObserver(token=token) as observer:
        if not (slack_events := list(observer.observe())):
            logger.info('Successfully checked Slack - no new messages found')
            return None

        # Create enriched events with AI analysis
        for event in slack_events:
            if event.hash in processed_hashes:
                logger.debug(f'Skipping already processed message with hash: {event.hash}')
                continue

            events.append(
                {
                    'type': event.source_type,
                    'timestamp': event.timestamp.isoformat(),
                    'hash': event.hash,
                    'channel': event.content['channel'],
                    'user': event.content['user'],
                    'text': event.content['text'],
                    'thread_ts': event.content.get('thread_ts'),
                    'permalink': event.content.get('permalink'),
                }
            )
            logger.info(
                f'New message in {event.content["channel"]} '
                f'from {event.content["user"]}: {event.content["text"][:50]}...'
            )

        if not events:
            logger.info('All messages have already been processed')
            return None

        # Store raw events first
        raw_summary = ObservationSummary(
            timestamp=datetime.now(UTC),
            summary='',
            events=events,
            source_types=['slack'],
        )
        storage.store_raw(raw_summary)

        # Create processed summary with AI analysis
        summary = ObservationSummary(
            timestamp=datetime.now(UTC),
            summary=run_agent_loop(
                'Create summary of Slack messages',
                agents=agents,
                instructions="""
                Review these Slack messages and create a concise summary.
                Group related messages by:
                1. Channel and thread context
                2. Topic similarity
                3. User interactions
                Highlight anything requiring attention or follow-up.
                """,
                context={'events': events},
                result_type=str,
            ),
            events=events,
            source_types=['slack'],
        )

        storage.store_processed(summary)
        return summary


@flow
def check_slack(storage: DiskStorage, agents: list[cf.Agent]) -> None:
    """Process Slack messages and store using storage abstraction"""
    logger.info_style('Checking Slack for 💬')
    logger.debug(f'Processing Slack messages with instructions: {slack_settings.instructions}')
    process_slack_observations(storage, agents)


@root_settings.hl.instance.require_approval()
def send_slack_message(channel: str, text: str) -> str | None:
    """Send a message to a Slack channel."""
    client = WebClient(token=slack_settings.bot_token)

    try:
        response = client.chat_postMessage(channel=channel, text=text)
        return f'Message sent to {channel}: {response["ts"]}'
    except SlackApiError as e:
        logger.error(f'Failed to send Slack message: {e.response["error"]}')
        raise
    except Exception as e:
        logger.error(f'Unexpected error: {e}')
        raise
