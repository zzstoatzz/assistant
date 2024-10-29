from datetime import UTC, datetime, timedelta

from app.settings import settings
from app.storage import DiskStorage
from app.types import CompactedSummary, ObservationSummary
from assistant.utilities.loggers import get_logger

logger = get_logger()


def get_storage() -> DiskStorage:
    return DiskStorage(settings.summaries_dir)


def load_summaries(hours: int = 24) -> tuple[list[ObservationSummary], list[CompactedSummary]]:
    """Load both recent and compact summaries"""
    storage = get_storage()
    cutoff = datetime.now(UTC) - timedelta(hours=hours)

    recent_summaries = []
    for summary_file in storage.get_processed():
        try:
            summary = ObservationSummary.model_validate_json(summary_file.read_text())
            if summary.timestamp.tzinfo is None:
                summary.timestamp = summary.timestamp.replace(tzinfo=UTC)
            if summary.timestamp > cutoff:
                recent_summaries.append(summary)
        except Exception as e:
            logger.error(f'Failed to load summary {summary_file.name}: {e}')
            continue

    compact_summaries = []
    for summary_file in storage.get_compact():
        try:
            summary = CompactedSummary.model_validate_json(summary_file.read_text())
            if summary.end_time.tzinfo is None:
                summary.end_time = summary.end_time.replace(tzinfo=UTC)
            if summary.end_time > cutoff:
                compact_summaries.append(summary)
        except Exception as e:
            logger.error(f'Failed to load compact summary {summary_file.name}: {e}')
            continue

    return recent_summaries, compact_summaries
