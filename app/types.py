from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Entity(BaseModel):
    """A persistent entity that emerges from observations"""

    id: str = Field(description='Unique identifier')
    type: Literal['user', 'repository', 'channel', 'topic'] = Field(description='Type of entity')
    source: Literal['github', 'slack', 'email'] = Field(description='Where this entity originated')

    name: str = Field(description='Human readable identifier')
    description: str = Field(description='Current understanding of this entity')

    first_seen: datetime = Field(description='When first observed')
    last_seen: datetime = Field(description='Last observation')
    last_updated: datetime = Field(description='Last description update')

    # Configurable importance threshold - entity is pruned when below this
    importance: float = Field(ge=0, le=1, description='Current importance score')

    # List of recent observation summaries that mention this entity
    recent_mentions: list[str] = Field(
        default_factory=list,
        description='IDs of recent summaries mentioning this entity',
        max_length=10,  # Keep only recent history
    )


class ObservationSummary(BaseModel):
    """Raw observation from information streams"""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    summary: str = Field(description='Human-readable summary of the observation')
    events: list[dict[str, Any]] = Field(description='Raw event data with source links')
    source_types: list[str] = Field(description='Types of sources (github, slack, etc)')
    day_id: str = Field(
        default_factory=lambda: datetime.now(UTC).strftime('%Y-%m-%d'), description='YYYY-MM-DD grouping key'
    )

    # Track entity mentions
    entity_mentions: list[str] = Field(default_factory=list, description='IDs of entities mentioned in these events')
    referenced_entities: list[Entity] = Field(
        default_factory=list, description='Loaded Entity objects for mentioned entities'
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

    empty: bool = Field(default=False, description='Whether this summary is empty')
