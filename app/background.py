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
    """Load raw summaries that need processing"""
    unprocessed = list(storage.get_unprocessed())
    if not unprocessed:
        return []

    loaded = []
    for path in unprocessed:
        try:
            summary = ObservationSummary.model_validate_json(path.read_text())
            loaded.append((path, summary))
        except Exception as e:
            logger.error(f'Failed to load summary {path.name}: {e}')
    return loaded


@task
def evaluate_for_pinboard(
    summaries: list[ObservationSummary], existing_compact: CompactedSummary | None, agents: list[cf.Agent]
) -> CompactedSummary | None:
    """Evaluate if recent observations should be added to historical pinboard"""
    return cf.run(
        'Evaluate if these events deserve a spot on the historical pinboard',
        agents=[agents[-1]],  # Use secretary as gatekeeper
        instructions="""
        Review these events and decide if they warrant historical preservation:
        1. Look for significant changes or milestones
        2. Consider long-term impact and relevance
        3. Evaluate if this adds new context to existing pins
        4. Preserve critical links and relationships
        5. Only create/update pins for truly noteworthy items

        If nothing is historically significant, return None.
        """,
        context={
            'recent_summaries': [s.model_dump() for s in summaries],
            'existing_pin': existing_compact.model_dump() if existing_compact else None,
            'user_identities': settings.user_identities,
        },
        result_type=CompactedSummary,
    )


@flow
def compress_observations(storage: DiskStorage, agents: list[cf.Agent]) -> None:
    """Process and consolidate observations"""
    logger.info('Compressing observations')

    # 1. Process raw summaries to processed/
    if loaded_summaries := load_unprocessed_summaries(storage):
        for path, summary in loaded_summaries:
            storage.store_processed(summary)
            path.rename(storage.processed_dir / path.name)

    # 2. Group processed summaries by day
    day_groups = {}
    for path in storage.get_processed():
        try:
            summary = ObservationSummary.model_validate_json(path.read_text())
            day_groups.setdefault(summary.day_id, []).append(summary)
        except Exception as e:
            logger.error(f'Failed to load processed summary {path.name}: {e}')

    # 3. Let secretary evaluate each day for historical significance
    for day_id, summaries in day_groups.items():
        # Check existing pin
        existing = None
        for path in storage.get_compact():
            try:
                compact = CompactedSummary.model_validate_json(path.read_text())
                if compact.end_time.date() == summaries[0].day_id:
                    existing = compact
                    break
            except Exception as e:
                logger.error(f'Failed to load compact summary {path.name}: {e}')

        # Let secretary decide if this should be pinned
        if compact_summary := evaluate_for_pinboard(summaries, existing, agents):
            storage.store_compact(compact_summary)
