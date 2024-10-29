from datetime import UTC, datetime

import controlflow as cf
from prefect import flow, task
from pydantic import BaseModel

from app.settings import settings
from app.storage import DiskStorage
from app.types import ObservationSummary
from assistant.observers.slack import SlackObserver
from assistant.utilities.loggers import get_logger

logger = get_logger('assistant.slack')


class RawEvents(BaseModel):
    timestamp: datetime
    source: str
    events: list


@task
def process_slack_observations(storage: DiskStorage, agents: list[cf.Agent]) -> ObservationSummary | None:
    """Process Slack messages and create a summary"""

    if not (token := settings.slack_bot_token):
        logger.error('Slack bot token is not set')
        return None

    # Load BOTH raw and processed messages to check for duplicates
    processed_messages = set()

    # Check processed directory
    for path in storage.get_processed():
        try:
            summary = ObservationSummary.model_validate_json(path.read_text())
            for event in summary.events:
                if event['type'] == 'slack':
                    msg_key = f"{event['id']}_{event['channel']}"
                    processed_messages.add(msg_key)
        except Exception as e:
            logger.error(f'Error loading processed summary {path}: {e}')

    # Also check raw directory
    for path in storage.get_unprocessed():
        try:
            summary = ObservationSummary.model_validate_json(path.read_text())
            for event in summary.events:
                if event['type'] == 'slack':
                    msg_key = f"{event['id']}_{event['channel']}"
                    processed_messages.add(msg_key)
        except Exception as e:
            logger.error(f'Error loading raw summary {path}: {e}')

    events = []
    with SlackObserver(token=token) as observer:
        events_list = list(observer.observe())
        if not events_list:
            logger.info('Successfully checked Slack - no new messages found')
            return None

        new_events = []
        for event in events_list:
            msg_key = f'{event.id}_{event.channel}'
            if msg_key not in processed_messages:
                new_events.append(event)
                events.append(
                    {
                        'type': 'slack',
                        'timestamp': datetime.now(UTC).isoformat(),
                        'channel': event.channel,
                        'sender': event.user,
                        'text': event.text,
                        'id': event.id,
                        'thread_ts': event.thread_ts,
                    }
                )
                logger.info(f'New message in {event.channel} from {event.user} [{msg_key}]: {event.text[:50]}...')
            else:
                logger.debug(f'Skipping already processed message: {msg_key}')

        if not new_events:
            logger.info('All messages have already been processed')
            return None

        # Store raw events immediately
        summary = ObservationSummary(timestamp=datetime.now(UTC), summary='', events=events, source_types=['slack'])
        storage.store_raw(summary)

    return summary


@flow
def check_slack(storage: DiskStorage, agents: list[cf.Agent]) -> None:
    """Process Slack messages and store using storage abstraction"""
    logger.info_style('Checking Slack for 💬')
    process_slack_observations(storage, agents)
