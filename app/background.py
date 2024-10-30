from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TypeAlias

import controlflow as cf
from prefect import flow, task

from app.settings import settings
from app.storage import DiskStorage
from app.types import CompactedSummary, ObservationSummary
from assistant.utilities.loggers import get_logger

logger = get_logger('assistant.background')

SummaryWithPath: TypeAlias = tuple[Path, ObservationSummary]
DailyGroups: TypeAlias = dict[str, list[ObservationSummary]]


@task
def load_unprocessed_summaries(storage: DiskStorage) -> list[SummaryWithPath]:
    """Load unprocessed summaries and their paths"""
    unprocessed = list(storage.get_unprocessed())
    if not unprocessed:
        logger.info('No unprocessed summaries found')
        return []

    loaded: list[SummaryWithPath] = []
    for path in unprocessed:
        try:
            summary = ObservationSummary.model_validate_json(path.read_text())
            loaded.append((path, summary))
        except Exception as e:
            logger.error(f'Failed to load summary {path.name}: {e}')
            continue

    return loaded


def _get_agent_names(parameters: dict[str, object]) -> str:
    """Format agent names for task run display"""
    agents = parameters.get('agents', [])
    if not isinstance(agents, Sequence):
        return 'unknown agents'
    return 'analyzing summaries with agent(s): ' + ', '.join(a.name for a in agents)


@task(task_run_name=_get_agent_names)
def analyze_summaries(summaries: list[ObservationSummary], agents: list[cf.Agent]) -> CompactedSummary | None:
    """Have agents analyze the summaries"""
    if not summaries:
        return None

    return cf.run(
        'Check if any of the summaries are interesting, reach out to the human if they are',
        agents=agents,
        context={'summaries': [s.model_dump() for s in summaries]},
        result_type=CompactedSummary,
    )


@task
def compact_summaries(
    summary_data: list[SummaryWithPath], agents: list[cf.Agent], extra_context: dict | None = None
) -> CompactedSummary:
    """Compress and organize summaries for efficient rendering"""
    daily_groups: DailyGroups = {}
    for _, summary in summary_data:
        daily_groups.setdefault(summary.day_id, []).append(summary)

    return cf.run(
        'create a compact summary that preserves important context',
        agents=agents,
        instructions="""
        when compacting summaries:
        1. always include relevant links in markdown format
        2. prioritize direct links to actionable items
        3. format should be concise but preserve context through links
        4. distinguish between the human's activity and others
        5. make it clear when summarizing the human's own actions
        """,
        context={
            'daily_groups': daily_groups,
            'user_identities': settings.user_identities,
            **(extra_context or {}),
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
            new_path = _get_unique_archive_path(storage, path)
            path.rename(new_path)
            logger.info(f'Successfully archived {path.name} to {new_path}')
        except Exception as e:
            logger.error(f'Failed to archive {path.name}: {e}')


def _get_unique_archive_path(storage: DiskStorage, path: Path) -> Path:
    """Generate a unique path for archiving a summary"""
    new_path = storage.processed_dir / path.name
    if new_path.exists():
        timestamp = datetime.now(UTC).strftime('%Y%m%d_%H%M%S')
        new_path = storage.processed_dir / f'{path.stem}_{timestamp}{path.suffix}'
    return new_path


@task
def load_compact_summaries(hours: int | None = None) -> list[CompactedSummary]:
    """Load compacted summaries, optionally filtered by time window"""
    compact_dir = settings.summaries_dir / 'compact'
    if not compact_dir.exists():
        return []

    cutoff = datetime.now(UTC) - timedelta(hours=hours) if hours else None
    summaries: list[CompactedSummary] = []

    for path in compact_dir.glob('compact_*.json'):
        try:
            summary = _load_and_normalize_summary(path)
            if not cutoff or summary.end_time > cutoff:
                summaries.append(summary)
        except Exception as e:
            logger.error(f'Failed to load compact summary {path.name}: {e}')
            continue

    return sorted(summaries, key=lambda s: (s.end_time, s.importance_score), reverse=True)


def _load_and_normalize_summary(path: Path) -> CompactedSummary:
    """Load a summary and ensure its timestamps are UTC"""
    summary = CompactedSummary.model_validate_json(path.read_text())
    if summary.end_time.tzinfo is None:
        summary.end_time = summary.end_time.replace(tzinfo=UTC)
    return summary


@flow
def compress_observations(storage: DiskStorage, agents: list[cf.Agent]) -> None:
    """Main flow for compressing observations"""
    logger.info('Compressing observations')
    if not (loaded_summaries := load_unprocessed_summaries(storage)):
        logger.info('No unprocessed summaries found')
        return

    paths = [p for p, _ in loaded_summaries]
    summaries = [s for _, s in loaded_summaries]

    analysis = analyze_summaries(summaries, agents)
    extra_context = {'analysis': analysis} if analysis else None

    if compact_summary := compact_summaries(loaded_summaries, agents, extra_context):
        store_compacted_summary(storage, compact_summary)
        archive_processed_summaries(storage, paths)
