from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from assistant.observer import BaseEvent, Observer
from assistant.utilities.loggers import get_logger

logger = get_logger('assistant.slack')


@dataclass
class SlackEvent(BaseEvent):
    """Slack message event data"""

    channel: str = field(default='')
    user: str = field(default='')
    text: str = field(default='')
    thread_ts: str | None = field(default=None)
    permalink: str | None = field(default=None)


class SlackObserver(BaseModel, Observer[dict[str, Any], SlackEvent]):
    """Slack implementation of the Observer protocol"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    token: str
    client: WebClient | None = None
    lookback_hours: int = 1  # How far back to look for messages

    def connect(self) -> None:
        """Initialize Slack client"""
        self.client = WebClient(token=self.token)

    def _get_channel_name(self, channel_id: str) -> str:
        """Get channel name from ID"""
        try:
            # Try public channel
            response = self.client.conversations_info(channel=channel_id)  # type: ignore
            return f"#{response['channel']['name']}"
        except SlackApiError:
            try:
                # Try private channel/DM
                response = self.client.conversations_info(channel=channel_id)  # type: ignore
                return f"@{response['channel']['name']}"
            except SlackApiError:
                return channel_id

    def _get_user_name(self, user_id: str) -> str:
        """Get username from ID"""
        try:
            response = self.client.users_info(user=user_id)  # type: ignore
            return response['user']['name']
        except SlackApiError:
            return user_id

    def observe(self) -> Iterator[SlackEvent]:
        """Stream Slack messages as events"""
        if not self.client:
            raise RuntimeError('Observer not connected')

        oldest = datetime.now(UTC) - timedelta(hours=self.lookback_hours)
        oldest_ts = oldest.timestamp()

        try:
            # Get list of channels the bot is a member of
            response = self.client.conversations_list(  # type: ignore
                types='public_channel,private_channel,im,mpim',
                exclude_archived=True,
                limit=1000,
                team_member_count=True,
            )

            channels = [
                channel
                for channel in response['channels']
                if channel.get('is_member', False)  # Only process channels the bot is a member of
            ]

            if not channels:
                logger.info('Bot is not a member of any channels. Invite the bot to channels to monitor them.')
                return

            for channel in channels:
                channel_id = channel['id']
                try:
                    history = self.client.conversations_history(  # type: ignore
                        channel=channel_id,
                        oldest=str(oldest_ts),
                    )

                    for message in history['messages']:
                        # Skip bot messages and system messages
                        if message.get('subtype') or not message.get('user'):
                            continue

                        # Get permalink for the message
                        try:
                            permalink_resp = self.client.chat_getPermalink(  # type: ignore
                                channel=channel_id, message_ts=message['ts']
                            )
                            permalink = permalink_resp.get('permalink')
                        except SlackApiError:
                            permalink = None

                        yield SlackEvent(
                            id=message['ts'],
                            source_type='slack',
                            channel=self._get_channel_name(channel_id),
                            user=self._get_user_name(message['user']),
                            text=message['text'],
                            thread_ts=message.get('thread_ts'),
                            permalink=permalink,
                            raw_source=message,
                        )

                except SlackApiError as e:
                    logger.error(f'Error accessing channel {channel_id}: {e}')

        except SlackApiError as e:
            logger.error(f'Error listing channels: {e}')

    def disconnect(self) -> None:
        """Clean up Slack client"""
        self.client = None
