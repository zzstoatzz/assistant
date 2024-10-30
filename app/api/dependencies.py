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


def load_summaries(hours: int) -> tuple[list[ObservationSummary], list[CompactedSummary]]:
    """Load recent and compact summaries within time window"""
    storage = DiskStorage(settings.summaries_dir)

    # Load processed summaries from the last N hours
    recent = []
    for path in storage.get_processed():
        try:
            summary = ObservationSummary.model_validate_json(path.read_text())
            if summary.timestamp > datetime.now(UTC) - timedelta(hours=hours):
                recent.append(summary)
        except Exception as e:
            logger.error(f'Failed to load summary {path.name}: {e}')

    # Load compact summaries
    compact = []
    for path in storage.get_compact():
        try:
            summary = CompactedSummary.model_validate_json(path.read_text())
            if summary.end_time > datetime.now(UTC) - timedelta(hours=hours):
                compact.append(summary)
        except Exception as e:
            logger.error(f'Failed to load compact summary {path.name}: {e}')

    return recent, compact


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
