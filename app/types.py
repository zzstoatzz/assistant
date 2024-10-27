from datetime import datetime
from typing import Any

from prefect.logging.loggers import get_logger
from pydantic import BaseModel

logger = get_logger()


class ObservationSummary(BaseModel):
    """Summary of observations from a time period"""

    timestamp: datetime
    summary: str
    events: list[dict[str, Any]]
    source_types: list[str]
