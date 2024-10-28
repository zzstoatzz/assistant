from datetime import datetime
from pathlib import Path
from typing import Any

import controlflow as cf
from prefect import flow, task

from app.settings import settings
from app.types import ObservationSummary
from assistant.utilities.loggers import get_logger

logger = get_logger()


def _get_agent_names(parameters: dict[str, Any]) -> str:
    return 'processing summaries with agent(s): ' + ', '.join(a.name for a in parameters['agents'])


def _get_summary_paths(parameters: dict[str, Any]) -> str:
    return f'archiving summary path(s): {", ".join(p.name for p in parameters["summary_paths"])}'


@task(task_run_name=_get_agent_names)
def process_summaries(agents: list[cf.Agent]) -> tuple[list[Path], Any]:
    """Process unread summaries and return paths of processed files"""
    summary_files = list(settings.summaries_dir.glob('summary_*.json'))
    unprocessed = [p for p in summary_files if p.parent == settings.summaries_dir]

    if not unprocessed:
        logger.info('No unprocessed summaries found')
        return [], None

    summaries = [ObservationSummary.model_validate_json(p.read_text()) for p in unprocessed]

    # Have secretary analyze them
    analysis = cf.run(
        'Check if any of the summaries are interesting, reach out to the human if they are',
        agents=agents,
        context={'summaries': [s.model_dump() for s in summaries]},
    )

    return unprocessed, analysis


@task(task_run_name=_get_summary_paths)
def archive_processed_summaries(summary_paths: list[Path]) -> None:
    """Move processed summaries to archive directory"""
    processed_dir = settings.processed_summaries_dir

    for path in summary_paths:
        try:
            # Ensure unique filename in case of collisions
            new_path = processed_dir / path.name
            if new_path.exists():
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                new_path = processed_dir / f'{path.stem}_{timestamp}{path.suffix}'

            # Move the file
            path.rename(new_path)
            logger.info(f'Archived summary: {path.name} -> {new_path.name}')

        except Exception as e:
            logger.error(f'Failed to archive {path.name}: {e}')


@flow
def check_observations(agents: list[cf.Agent]) -> None:
    """Enhanced observation checking flow"""
    # Process summaries and get list of processed files
    paths, analysis = process_summaries(agents)

    # Archive processed files if we have any
    if paths:
        archive_processed_summaries(paths)

    return analysis
