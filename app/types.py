from datetime import datetime
from typing import Any

from prefect.logging.loggers import get_logger
from pydantic import BaseModel, Field

logger = get_logger()


class ObservationSummary(BaseModel):
    """Summary of observations from a time period"""

    timestamp: datetime
    summary: str
    events: list[dict[str, Any]]
    source_types: list[str]


class CompactionResult(BaseModel):
    """The result of compacting multiple summaries"""

    summary: str = Field(description='Brief high-level overview of the time period')
    key_points: list[str] = Field(description='Most important individual points to retain')
    importance_score: float = Field(description='How critical this information is (0-1)', ge=0, le=1)


class CompactedSummary(BaseModel):
    """A condensed summary of a time period"""

    start_time: datetime
    end_time: datetime
    summary: str
    key_points: list[str]
    source_types: list[str]
    importance_score: float
