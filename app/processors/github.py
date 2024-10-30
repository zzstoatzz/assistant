from datetime import datetime
from pathlib import Path
from typing import Any

import controlflow as cf
import httpx
from jinja2 import Template
from prefect import flow, task
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.settings import settings as root_settings
from app.storage import DiskStorage
from app.types import ObservationSummary
from assistant.observers.github import GitHubEventFilter, GitHubObserver
from assistant.utilities.loggers import get_logger

logger = get_logger('assistant.github')


class GitHubSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='GITHUB_', extra='ignore')

    enabled: bool = Field(default=False, description='Enable GitHub processing')
    token: str = Field(description='GitHub API token')
    check_interval_seconds: int = Field(default=300, ge=10)
    event_filters_path: Path = Field(default=Path(__file__).parent.parent / 'github_event_filters.json')

    agent_instructions: str = Field(
        default="""
        Review these GitHub notifications and create a concise summary.
        Group related items by repository and highlight anything urgent.
        """
    )

    @property
    def event_filters(self) -> list[GitHubEventFilter]:
        """Load event filters from JSON file"""
        if not self.token or not self.event_filters_path.exists():
            logger.warning(f'No token or filter file not found at {self.event_filters_path}')
            return []
        try:
            import json

            data = json.loads(self.event_filters_path.read_text())
            filters = [GitHubEventFilter(**f) for f in data]
            return filters
        except Exception as e:
            logger.error(f'Failed to load GitHub event filters: {e}')
            return []


settings = GitHubSettings()  # type: ignore


def _get_agent_names(parameters: dict[str, Any]) -> str:
    return 'processing GitHub notifications with agent(s): ' + ', '.join(a.name for a in parameters['agents'])


@task(task_run_name=_get_agent_names)
def process_github_observations(
    storage: DiskStorage,
    agents: list[cf.Agent],
    event_filters: list[GitHubEventFilter],
    instructions: str | None = None,
) -> ObservationSummary | None:
    """Process GitHub notifications and create a summary"""

    events = []
    with GitHubObserver(token=settings.token, filters=event_filters) as observer:
        if not (events_list := list(observer.observe())):
            logger.info('Successfully checked GitHub - no new notifications')
            return None

        # Create events first
        for event in events_list:
            events.append(
                {
                    'type': event.type,
                    'timestamp': datetime.now(root_settings.tz).isoformat(),
                    'hash': event.id,
                    'title': event.title,
                    'repository': event.repository,
                    'reason': event.reason,
                    'url': event.url,
                }
            )
            logger.info_kv(event.repository, event.title)

        # Store raw events
        raw_summary = ObservationSummary(
            timestamp=datetime.now(root_settings.tz),  # Use Chicago time
            summary='',  # Empty summary for raw storage
            events=events,
            source_types=['github'],
        )
        storage.store_raw(raw_summary)

    # Create and store processed summary
    summary = ObservationSummary(
        timestamp=datetime.now(root_settings.tz),
        summary=cf.run(
            (
                'Create pretty, concise, summary of new GitHub notifications for humans. '
                'Always use html links instead of api links.'
            ),
            agents=agents,
            instructions=instructions or settings.agent_instructions,
            context={'events': events},
            result_type=str,
        ),
        events=events,
        source_types=['github'],
    )

    storage.store_processed(summary)
    return summary


@flow
def check_github(
    storage: DiskStorage,
    agents: list[cf.Agent],
    instructions: str | None = None,
) -> None:
    """Process GitHub notifications and store using storage abstraction"""

    filter_template = Template("""{{ repo }}
    {%- if event_types %} │ {{ event_types|join(', ') }}{% endif -%}
    {%- if reasons %} │ {{ reasons|join(', ') }}{% endif -%}
    {%- if branch %} │ {{ branch }}{% endif %}""")

    if event_filters := settings.event_filters:
        logger.info_style('Checking GitHub for 🛎️')
        for github_filter in event_filters:
            filter_desc = filter_template.render(
                repo=f"Repository: {', '.join(github_filter.repositories)}",
                event_types=github_filter.event_types,
                reasons=github_filter.reasons,
                branch=github_filter.branch,
            )
            logger.info_style(filter_desc)
    else:
        logger.warning_style('No GitHub event filters found. You may get too many notifications.')
        event_filters = []

    process_github_observations(storage, agents, event_filters, instructions)


@root_settings.hl.instance.require_approval()
def create_github_issue(repository_name: str, title: str, body: str) -> str | None:
    """Create a GitHub issue using the GitHub API."""
    url = f'https://api.github.com/repos/{repository_name}/issues'
    headers = {
        'Authorization': f'token {settings.token}',
        'Accept': 'application/vnd.github.v3+json',
    }
    data = {'title': title, 'body': body}

    try:
        response = httpx.post(url, headers=headers, json=data)
        response.raise_for_status()
        issue_url = response.json().get('html_url')
        return f'Issue created: {issue_url}'
    except httpx.HTTPStatusError as e:
        logger.error(f'Failed to create GitHub issue: {e.response.text}')
        raise
    except Exception as e:
        logger.error(f'Unexpected error: {e}')
        raise
