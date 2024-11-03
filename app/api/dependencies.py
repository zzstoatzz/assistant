from datetime import datetime, timedelta
from typing import TypeAlias

from app.settings import settings
from app.sources.email import email_settings
from app.sources.github import github_settings
from app.sources.slack import slack_settings
from app.storage import DiskStorage
from app.types import CompactedSummary, ObservationSummary
from assistant.utilities.loggers import get_logger

logger = get_logger()

ProcessorSummaries: TypeAlias = tuple[list[ObservationSummary], list[CompactedSummary]]


def get_storage() -> DiskStorage:
    """Get storage instance"""
    return DiskStorage()


def load_summaries(hours: int = 24) -> tuple[list[ObservationSummary], list[CompactedSummary]]:
    """Load recent summaries and historical pins"""
    storage = DiskStorage()
    cutoff = datetime.now(settings.tz) - timedelta(hours=hours)

    recent_summaries = []
    for path in storage.get_processed():
        try:
            summary = ObservationSummary.model_validate_json(path.read_text())
            # Ensure timestamp is timezone-aware
            if not summary.timestamp.tzinfo:
                summary.timestamp = summary.timestamp.replace(tzinfo=settings.tz)
            if summary.timestamp >= cutoff:
                recent_summaries.append(summary)
        except Exception as e:
            logger.error(f'Failed to load summary {path}: {e}')

    compact_summaries = []
    for path in storage.get_compact():
        try:
            summary = CompactedSummary.model_validate_json(path.read_text())
            # Ensure timestamps are timezone-aware
            if not summary.start_time.tzinfo:
                summary.start_time = summary.start_time.replace(tzinfo=settings.tz)
            if not summary.end_time.tzinfo:
                summary.end_time = summary.end_time.replace(tzinfo=settings.tz)
            compact_summaries.append(summary)
        except Exception as e:
            logger.error(f'Failed to load compact summary {path}: {e}')

    return recent_summaries, compact_summaries


def get_enabled_sources() -> list[str]:
    """Get list of enabled sources"""
    enabled = []
    if email_settings.enabled:
        enabled.append('email')
    if github_settings.enabled:
        enabled.append('github')
    if slack_settings.enabled:
        enabled.append('slack')
    return enabled
