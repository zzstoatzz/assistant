from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    log_level: str = 'INFO'

    @model_validator(mode='after')
    def ensure_logging_setup(self) -> Self:
        from assistant.utilities.loggers import setup_logging

        setup_logging(self.log_level)
        return self


settings = Settings()
