from datetime import UTC, datetime
from typing import Any

from prefect.logging.loggers import get_logger
from pydantic import BaseModel, Field

logger = get_logger()


class ObservationSummary(BaseModel):
    """Summary of observations from a time period"""

    summary: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    events: list[dict[str, Any]]
    source_types: list[str]


class CompactionResult(BaseModel):
    """The result of compacting multiple summaries"""

    summary: str = Field(description='Brief high-level overview of the time period')
    key_points: list[str] = Field(description='Most important individual points to retain')
    importance_score: float = Field(description='How critical this information is (0-1)', ge=0, le=1)


class CompactedSummary(BaseModel):
    """A condensed summary of observations over a time period"""

    summary: str = Field(description='Consolidated summary of critical events and changes')
    start_time: datetime = Field(description='Timestamp of earliest observation in this summary')
    end_time: datetime = Field(description='Timestamp of latest observation in this summary')
    importance_score: float = Field(
        description='Score from 0-1 indicating historical significance',
        ge=0,
        le=1,
    )
    source_types: list[str] = Field(description='Types of sources that contributed to this summary')
