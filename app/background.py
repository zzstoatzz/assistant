from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import controlflow as cf
from prefect import flow, task

from app.settings import settings
from app.storage import DiskStorage
from app.types import CompactedSummary, ObservationSummary
from assistant.utilities.loggers import get_logger

logger = get_logger('assistant.background')


@task
def load_unprocessed_summaries(storage: DiskStorage) -> list[tuple[Path, ObservationSummary]]:
    """Load unprocessed summaries and their paths"""
    unprocessed = list(storage.get_unprocessed())

    if not unprocessed:
        logger.info('No unprocessed summaries found')
        return []

    loaded = []
    for path in unprocessed:
        try:
            summary = ObservationSummary.model_validate_json(path.read_text())
            loaded.append((path, summary))
        except Exception as e:
            logger.error(f'Failed to load summary {path.name}: {e}')
            continue

    return loaded


def _get_agent_names(parameters: dict[str, Any]) -> str:
    return 'analyzing summaries with agent(s): ' + ', '.join(a.name for a in parameters['agents'])


@task(task_run_name=_get_agent_names)
def analyze_summaries(summaries: list[ObservationSummary], agents: list[cf.Agent]) -> Any:
    """Have agents analyze the summaries"""
    if not summaries:
        return None

    return cf.run(
        'Check if any of the summaries are interesting, reach out to the human if they are',
        agents=agents,
        context={'summaries': [s.model_dump() for s in summaries]},
    )


@task
def compact_summaries(
    summary_data: list[tuple[Path, ObservationSummary]], agents: list[cf.Agent]
) -> CompactedSummary | None:
    """Compact multiple summaries using LSM-tree inspired approach"""
    if not summary_data:
        return None

    existing_summaries = load_compact_summaries()

    # Ensure all timestamps are timezone-aware before sorting
    summaries = []
    for _, summary in summary_data:
        if summary.timestamp.tzinfo is None:
            # If timestamp is naive, assume UTC
            summary.timestamp = summary.timestamp.replace(tzinfo=UTC)
        summaries.append(summary)

    summaries.sort(key=lambda s: s.timestamp)

    return cf.run(
        'Condense observations to only critical information',
        agents=agents,
        instructions="""
        Create a historically significant summary that will persist in long-term memory.

        Think like a database with multiple tiers of storage:

        Tier 1 (Hot/Recent) - Last 24 hours:
        - CI failures on main/2.x branches
        - Critical security issues
        - Major feature releases

        Tier 2 (Warm/Weekly) - Last 7 days:
        - Significant architectural changes
        - Breaking changes
        - Important deprecations

        Tier 3 (Cold/Historical) - Long-term:
        - Major version releases
        - Critical security patches
        - Fundamental architectural shifts

        Guidelines:
        - Use precise timestamps for historically significant events
        - Link to permanent references (commits, tags, releases)
        - Consolidate repeated information
        - Drop transient issues that were quickly resolved
        """,
        context={
            'summaries': [s.model_dump() for s in summaries],
            'existing_summaries': [s.model_dump() for s in existing_summaries],
            'start_time': min(s.timestamp for s in summaries),
            'end_time': max(s.timestamp for s in summaries),
        },
        result_type=CompactedSummary,
    )


@task
def store_compacted_summary(storage: DiskStorage, summary: CompactedSummary) -> None:
    """Store a compacted summary"""
    storage.store_compact(summary)


@task
def archive_processed_summaries(storage: DiskStorage, paths: list[Path]) -> None:
    """Move processed summaries to processed directory"""
    for path in paths:
        try:
            new_path = storage.processed_dir / path.name
            if new_path.exists():
                timestamp = datetime.now(UTC).strftime('%Y%m%d_%H%M%S')
                new_path = storage.processed_dir / f'{path.stem}_{timestamp}{path.suffix}'

            path.rename(new_path)
            logger.info(f'Successfully archived {path.name} to {new_path}')
        except Exception as e:
            logger.error(f'Failed to archive {path.name}: {e}')


@task
def load_compact_summaries(hours: int | None = None) -> list[CompactedSummary]:
    """Load compacted summaries, optionally filtered by time window"""
    compact_dir = settings.summaries_dir / 'compact'
    if not compact_dir.exists():
        return []

    summaries = []
    cutoff = datetime.now(UTC) - timedelta(hours=hours) if hours else None

    for path in compact_dir.glob('compact_*.json'):
        try:
            summary = CompactedSummary.model_validate_json(path.read_text())
            # Ensure end_time is timezone-aware
            if summary.end_time.tzinfo is None:
                summary.end_time = summary.end_time.replace(tzinfo=UTC)
            if not cutoff or summary.end_time > cutoff:
                summaries.append(summary)
        except Exception as e:
            logger.error(f'Failed to load compact summary {path.name}: {e}')
            continue

    return sorted(summaries, key=lambda s: (s.end_time, s.importance_score), reverse=True)


@flow
def compress_observations(storage: DiskStorage, agents: list[cf.Agent]) -> None:
    """Main flow for compressing observations"""
    logger.info('Compressing observations')
    if not (loaded_summaries := load_unprocessed_summaries(storage)):
        logger.info('No unprocessed summaries found')
        return None

    paths = [p for p, _ in loaded_summaries]
    summaries = [s for _, s in loaded_summaries]

    analysis = analyze_summaries(summaries, agents)

    if compact_summary := compact_summaries(loaded_summaries, agents):
        store_compacted_summary(storage, compact_summary)

    archive_processed_summaries(storage, paths)

    return analysis
