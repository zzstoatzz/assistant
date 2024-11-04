from zoneinfo import ZoneInfo

from pydantic import computed_field, model_validator
from pydantic_settings import BaseSettings
from typing_extensions import Self


class Settings(BaseSettings):
    log_level: str = 'INFO'
    timezone: str = 'America/Chicago'

    @computed_field
    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @model_validator(mode='after')
    def ensure_logging_setup(self) -> Self:
        from assistant.utilities.loggers import setup_logging

        setup_logging(self.log_level)
        return self


settings = Settings()
