from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict

from assistant.observer import BaseEvent, Observer
from assistant.utilities.loggers import get_logger

logger = get_logger('observer.github')


@dataclass
class GitHubEvent(BaseEvent):
    """GitHub notification event data"""

    title: str = field(default='No Title')
    repository: str = field(default='')
    type: str = field(default='')
    reason: str = field(default='')
    url: str = field(default='')

    def __post_init__(self) -> None:
        """Ensure content is populated before hashing"""
        self.content = {
            'title': self.title,
            'repository': self.repository,
            'type': self.type,
            'reason': self.reason,
            'url': self.url,
        }
        super().__post_init__()


@dataclass
class GitHubEventFilter:
    """Configuration for filtering GitHub notifications"""

    repositories: list[str] = field(default_factory=list)
    event_types: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    branch: str | None = None

    def matches(self, notification: dict[str, Any]) -> bool:
        """Return True if notification matches filter criteria"""
        # Repository matching (exact matches)
        if self.repositories:
            repo_name = notification['repository']['full_name']
            if repo_name not in self.repositories:
                return False

        # Event type matching
        if self.event_types and notification['subject']['type'] not in self.event_types:
            return False

        # Reason matching
        if self.reasons and notification['reason'] not in self.reasons:
            return False

        # Branch matching (only for CheckSuite events)
        if (
            self.branch
            and notification['subject']['type'] == 'CheckSuite'
            and 'head' in notification['subject']  # Ensure we have the data
            and self.branch != notification['subject']['head']['ref']  # Actual branch reference
        ):
            return False

        return True


class GitHubObserver(BaseModel, Observer[dict[str, Any], GitHubEvent]):
    """GitHub implementation of the Observer protocol"""

    model_config: ConfigDict = ConfigDict(arbitrary_types_allowed=True)

    token: str
    client: httpx.Client | None = None
    filters: list[GitHubEventFilter] = []

    def connect(self) -> None:
        self.client = httpx.Client(
            base_url='https://api.github.com',
            headers={
                'Authorization': f'Bearer {self.token}',
                'Accept': 'application/vnd.github.v3+json',
                'X-GitHub-Api-Version': '2022-11-28',
            },
        )

    def observe(self) -> Iterator[GitHubEvent]:
        """Stream filtered GitHub notifications as events"""
        if not self.client:
            raise RuntimeError('Observer not connected')

        response = self.client.get('/notifications', params={'all': False})
        response.raise_for_status()
        notifications = response.json()

        logger.info(f'Received {len(notifications)} notifications from GitHub')

        for notification in notifications:
            logger.debug(
                f"Processing notification: repo={notification['repository']['full_name']}, "
                f"type={notification['subject']['type']}, "
                f"reason={notification['reason']}"
            )

            if self.filters:
                for f in self.filters:
                    matches = f.matches(notification)
                    logger.debug(
                        f'Filter check: repo={f.repositories}, types={f.event_types}, '
                        f'reasons={f.reasons}, branch={f.branch} -> matches={matches}'
                    )
                if not any(f.matches(notification) for f in self.filters):
                    logger.debug('Notification filtered out - no matching filters')
                    continue

            yield GitHubEvent(
                id=notification['id'],
                source_type='github',
                title=notification['subject']['title'],
                repository=notification['repository']['full_name'],
                type=notification['subject']['type'],
                reason=notification['reason'],
                url=notification['subject']['url'],
                raw_source=notification,
            )

            # Mark as read after processing
            self.client.patch(f"/notifications/threads/{notification['id']}", json={'read': True})

    def disconnect(self) -> None:
        if self.client:
            self.client.close()
        self.client = None
