from datetime import UTC, datetime
from typing import Any

import controlflow as cf
import httpx
from jinja2 import Template
from prefect import flow, task
from pydantic import TypeAdapter

from app.settings import settings
from app.storage import DiskStorage
from app.types import ObservationSummary
from assistant.observers.github import GitHubEventFilter, GitHubObserver
from assistant.utilities.loggers import get_logger

logger = get_logger('assistant.github')


def _get_agent_names(parameters: dict[str, Any]) -> str:
    return 'processing GitHub notifications with agent(s): ' + ', '.join(a.name for a in parameters['agents'])


@task(task_run_name=_get_agent_names)
def process_github_observations(
    storage: DiskStorage, filters: list[GitHubEventFilter], agents: list[cf.Agent], instructions: str | None = None
) -> ObservationSummary | None:
    """Process GitHub notifications and create a summary"""

    events = []
    with GitHubObserver(token=settings.github_token, filters=filters) as observer:
        if not (events_list := list(observer.observe())):
            logger.info('Successfully checked GitHub - no new notifications found')
            return None

        # Create events first
        for event in events_list:
            events.append(
                e := {
                    'type': 'github',
                    'timestamp': datetime.now().isoformat(),
                    'title': event.title,
                    'repository': event.repository,
                    'notification_type': event.type,
                    'reason': event.reason,
                    'url': event.url,
                }
            )
            logger.info_kv(e['repository'], e['title'])

        # Store raw events as ObservationSummary
        raw_summary = ObservationSummary(
            timestamp=datetime.now(UTC),
            summary='',  # Empty summary for raw storage
            events=events,
            source_types=['github'],
        )
        storage.store_raw(raw_summary)

    # Create and store processed summary
    summary = ObservationSummary(
        timestamp=datetime.now(UTC),
        summary=cf.run(
            'Create summary of new GitHub notifications',
            agents=agents,
            instructions=instructions
            or """
            Review these GitHub notifications and create a concise summary.
            Group related items by repository and highlight anything urgent or requiring immediate attention.
            """,
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
    github_filters: list[GitHubEventFilter] | None = None,
) -> None:
    """Process GitHub notifications and store using storage abstraction"""
    filter_template = Template("""{{ repo }}
    {%- if event_types %} │ {{ event_types|join(', ') }}{% endif -%}
    {%- if reasons %} │ {{ reasons|join(', ') }}{% endif -%}
    {%- if branch %} │ {{ branch }}{% endif %}""")

    if event_filters := TypeAdapter(list[GitHubEventFilter]).validate_python(
        github_filters or settings.github_event_filters
    ):
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

    process_github_observations(storage, event_filters, agents, instructions)


@settings.hl.instance.require_approval()
def create_github_issue(repository_name: str, title: str, body: str) -> str | None:
    """Create a GitHub issue using the GitHub API."""
    url = f'https://api.github.com/repos/{repository_name}/issues'
    headers = {
        'Authorization': f'token {settings.github_token}',
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
