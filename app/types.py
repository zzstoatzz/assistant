from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class ObservationSummary(BaseModel):
    """Raw observation from information streams"""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    summary: str = Field(description='Human-readable summary of the observation')
    events: list[dict[str, Any]] = Field(description='Raw event data with source links')
    source_types: list[str] = Field(description='Types of sources (github, slack, etc)')
    day_id: str = Field(
        default_factory=lambda: datetime.now(UTC).strftime('%Y-%m-%d'), description='YYYY-MM-DD grouping key'
    )


class CompactedSummary(BaseModel):
    """Historical record preserving important context"""

    summary: str = Field(description='Consolidated summary with markdown links to sources')
    start_time: datetime = Field(description='Start of observation window')
    end_time: datetime = Field(description='End of observation window')
    key_points: list[str] = Field(description='Critical points worth preserving', default_factory=list)
    importance_score: float = Field(description='Historical significance (0-1)', ge=0, le=1)
    source_types: list[str] = Field(description='Source types in this summary')
    day_id: str = Field(description='YYYY-MM-DD this summary belongs to')
