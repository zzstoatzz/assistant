from datetime import UTC, datetime, timedelta
from typing import TypeAlias

from app.processors.email import settings as email_settings
from app.processors.github import settings as github_settings
from app.processors.slack import settings as slack_settings
from app.settings import settings
from app.storage import DiskStorage
from app.types import CompactedSummary, ObservationSummary
from assistant.utilities.loggers import get_logger

logger = get_logger()

ProcessorSummaries: TypeAlias = tuple[list[ObservationSummary], list[CompactedSummary]]


def get_storage() -> DiskStorage:
    return DiskStorage(settings.summaries_dir)


def load_summaries(hours: int = 24) -> ProcessorSummaries:
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


def get_enabled_processors() -> list[str]:
    """Get list of enabled processors"""
    enabled = []
    if email_settings.enabled:
        enabled.append('email')
    if github_settings.enabled:
        enabled.append('github')
    if slack_settings.enabled:
        enabled.append('slack')
    return enabled
