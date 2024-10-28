from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict

from assistant.observer import BaseEvent, Observer


@dataclass
class GitHubEvent(BaseEvent):
    """GitHub notification event data"""

    title: str = field(default='No Title')
    repository: str = field(default='')
    type: str = field(default='')
    reason: str = field(default='')
    url: str = field(default='')


class GitHubObserver(BaseModel, Observer[dict[str, Any], GitHubEvent]):
    """GitHub implementation of the Observer protocol"""

    model_config: ConfigDict = ConfigDict(arbitrary_types_allowed=True)

    token: str
    client: httpx.Client | None = None

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
        """Stream unread GitHub notifications as events"""
        if not self.client:
            raise RuntimeError('Observer not connected')

        response = self.client.get('/notifications', params={'all': False})
        response.raise_for_status()
        notifications = response.json()

        for notification in notifications:
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
