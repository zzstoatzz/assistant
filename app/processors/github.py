from datetime import datetime
from typing import Any

import controlflow as cf
from prefect import flow, task
from prefect.logging import get_logger

from app.settings import settings
from app.types import ObservationSummary
from assistant.observers.github import GitHubEventFilter, GitHubObserver

logger = get_logger()


def _get_agent_names(parameters: dict[str, Any]) -> str:
    return 'processing GitHub notifications with agent(s): ' + ', '.join(a.name for a in parameters['agents'])


@task(task_run_name=_get_agent_names)
def process_github_observations(agents: list[cf.Agent], instructions: str | None = None) -> ObservationSummary | None:
    """Process GitHub notifications and create a summary"""
    logger = get_logger()

    filters = [
        # Main branch CI activity
        GitHubEventFilter(
            repositories=['PrefectHQ/prefect'],
            event_types=['CheckSuite'],
            reasons=['ci_activity'],
            branch='main',
        ),
        # Core repo PR activity
        GitHubEventFilter(
            repositories=['PrefectHQ/prefect'],
            event_types=['PullRequest'],
            reasons=['review_requested', 'mention', 'comment', 'state_change'],
        ),
        # Core repo Issue activity
        GitHubEventFilter(
            repositories=['PrefectHQ/prefect'],
            event_types=['Issue'],
            reasons=['mention', 'comment', 'assigned', 'labeled'],
        ),
    ]

    events = []
    with GitHubObserver(token=settings.github_token, filters=filters) as observer:
        # Get all events at once and break if none
        if not (events_list := list(observer.observe())):
            return None

        # Process events if we have them
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
            logger.info(f'{e["repository"]}: {e["title"]}')

    # Use the monitor agent to create a summary
    summary = cf.run(
        'Create summary of new GitHub notifications',
        agents=agents,
        instructions=(
            instructions
            or """
        Review these GitHub notifications and create a concise summary.
        Group related items by repository and highlight anything urgent or requiring immediate attention.
        """
        ),
        context={'events': events},
        result_type=str,
    )

    return ObservationSummary(summary=summary, events=events, source_types=['github'])


@flow
def check_github(agents: list[cf.Agent], instructions: str | None = None) -> None:
    """Process GitHub notifications and save summary to disk"""
    if summary := process_github_observations(agents, instructions):
        summary_path = settings.summaries_dir / f'summary_{summary.timestamp:%Y%m%d_%H%M%S}.json'
        summary_path.write_text(summary.model_dump_json(indent=2))
