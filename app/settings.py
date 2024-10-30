from functools import partial
from pathlib import Path
from typing import Annotated, Self

from prefect.types import validate_set_T_from_delim_string
from pydantic import BeforeValidator, Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Names = Annotated[
    str | list[str] | set[str] | None,
    BeforeValidator(partial(validate_set_T_from_delim_string, type_=str)),
]
Emails = Annotated[
    str | list[str] | set[str] | None,
    BeforeValidator(partial(validate_set_T_from_delim_string, type_=str)),
]


class UserIdentity(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='USER_IDENTITY_')

    names: Names = Field(default_factory=list)
    emails: Emails = Field(default_factory=list)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env', env_file_encoding='utf-8', extra='ignore', env_prefix='ASSISTANT_'
    )

    # Core settings
    host: str = Field(default='0.0.0.0')
    port: int = Field(default=8000, ge=1024, le=65535)
    app_dir: Path = Field(default=Path(__file__).parent)
    log_level: str = Field(default='INFO')

    # User identity
    user_identities: list[UserIdentity] = Field(default=[])
    # Observation settings
    observation_check_interval_seconds: int = Field(default=300, ge=10, examples=[30, 120, 600])

    @computed_field
    @property
    def templates_dir(self) -> Path:
        return self.app_dir / 'templates'

    @computed_field
    @property
    def static_dir(self) -> Path:
        return self.app_dir / 'static'

    @computed_field
    @property
    def summaries_dir(self) -> Path:
        return self.app_dir / 'summaries'

    @model_validator(mode='after')
    def set_log_level(self) -> Self:
        from assistant.utilities.loggers import setup_logging

        setup_logging(self.log_level)
        return self


settings = Settings()
