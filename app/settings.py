import os
from functools import partial
from pathlib import Path
from typing import Annotated, Self
from zoneinfo import ZoneInfo

from humanlayer import ContactChannel, HumanLayer, SlackContactChannel
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


def get_default_contact_channel() -> ContactChannel | None:
    if not (testing_user := os.getenv('TESTING_USER')):
        return None

    return ContactChannel(
        slack=SlackContactChannel(
            channel_or_user_id='',
            context_about_channel_or_user=f'a dm with {testing_user.lower()}',
            experimental_slack_blocks=True,
        )
    )


class HumanLayerSettings(BaseSettings):
    """Settings for the HumanLayer"""

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    slack: ContactChannel | None = Field(default_factory=get_default_contact_channel)

    @computed_field
    @property
    def instance(self) -> HumanLayer:
        """HumanLayer instance"""
        return HumanLayer(contact_channel=self.slack)


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
    timezone: str = Field(default='America/Chicago')

    @computed_field
    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    user_identity: UserIdentity = Field(default_factory=UserIdentity)

    # Observation settings
    observation_check_interval_seconds: int = Field(default=300, ge=10, examples=[30, 120, 600])
    hl: HumanLayerSettings = Field(default_factory=HumanLayerSettings)

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

    @computed_field
    @property
    def entities_dir(self) -> Path:
        return self.app_dir / 'entities'

    @model_validator(mode='after')
    def set_log_level(self) -> Self:
        from assistant.utilities.loggers import setup_logging

        setup_logging(self.log_level)
        return self

    @model_validator(mode='after')
    def create_dirs(self) -> Self:
        for dir in [
            self.summaries_dir,
            self.entities_dir,
        ]:
            if not dir.exists():
                dir.mkdir(parents=True, exist_ok=True)
        return self


settings = Settings()
