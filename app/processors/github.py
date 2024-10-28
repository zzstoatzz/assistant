from datetime import datetime

import controlflow as cf
from prefect import flow, task
from prefect.logging import get_logger

from app.settings import settings
from app.types import ObservationSummary
from assistant.observers.github import GitHubObserver

logger = get_logger()


@task
def process_github_observations(agents: list[cf.Agent]) -> ObservationSummary | None:
    """Process GitHub notifications and create a summary"""
    logger = get_logger()

    events = []
    with GitHubObserver(token=settings.github_token) as observer:
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
        instructions="""
        Review these GitHub notifications and create a concise summary.
        Group related items by repository and highlight anything urgent or requiring immediate attention.
        """,
        context={'events': events},
        result_type=str,
    )

    return ObservationSummary(timestamp=datetime.now(), summary=summary, events=events, source_types=['github'])


@flow
def check_github(agents: list[cf.Agent]) -> None:
    """Process GitHub notifications and save summary to disk"""
    if summary := process_github_observations(agents):
        summary_path = settings.summaries_dir / f'summary_{summary.timestamp:%Y%m%d_%H%M%S}.json'
        summary_path.write_text(summary.model_dump_json(indent=2))
