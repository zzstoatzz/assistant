from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict

from assistant.observer import BaseEvent, Observer
from assistant.utilities.loggers import get_logger

logger = get_logger('assistant.github')


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
        """Return True if this filter matches the notification"""
        repo = notification['repository']['full_name']
        type = notification['subject']['type']
        reason = notification['reason']

        # Log each check separately to see which criteria is failing
        repo_match = repo in self.repositories
        type_match = type in self.event_types
        reason_match = reason in self.reasons

        if not any([repo_match, type_match, reason_match]):
            logger.debug(f'Skipped {repo} - no criteria matched')
            return False

        matches = repo_match and type_match and reason_match
        if matches:
            logger.debug(f'✓ Matched: {repo} | {type} | {reason}')
        else:
            logger.debug(f'✗ Failed: {repo} ({repo_match}) | {type} ({type_match}) | {reason} ({reason_match})')

        return matches


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

        for notification in notifications:
            # Check once if ANY filter matches
            matched = False
            for f in self.filters:
                if f.matches(notification):
                    matched = True
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
                    self.client.patch(f"/notifications/threads/{notification['id']}", json={'read': True})
                    break  # Stop checking other filters once we match

            if not matched:
                logger.debug('Skipped notification - no filters matched')

    def disconnect(self) -> None:
        if self.client:
            self.client.close()
        self.client = None
