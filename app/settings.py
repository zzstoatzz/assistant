import os
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Annotated, Self
from zoneinfo import ZoneInfo

from humanlayer import ContactChannel, HumanLayer, SlackContactChannel
from prefect.types import LogLevel, validate_set_T_from_delim_string
from pydantic import BeforeValidator, Field, IPvAnyAddress, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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


SetOfStrings = Annotated[
    str | list[str] | set[str] | None,
    BeforeValidator(partial(validate_set_T_from_delim_string, type_=str)),
]


class UserIdentity(BaseSettings):
    """User identity settings

    You can set these in .env like:

    USER_IDENTITY_NAMES=nate,zzstoatzz
    USER_IDENTITY_EMAILS=foo@bar.com,other@domain.com

    or if needed, set them directly in the Settings object:
    ```python
    settings.user_identity.names = ['nate', 'zzstoatzz']
    settings.user_identity.emails = ['foo@bar.com', 'other@domain.com']
    ```
    """

    model_config = SettingsConfigDict(env_prefix='USER_IDENTITY_')

    names: SetOfStrings = Field(
        default_factory=set,
        description='Aliases that should be used to identify the user',
        examples=['nate,zzstoatzz', {'nate', 'zzstoatzz'}],
    )
    emails: SetOfStrings = Field(
        default_factory=set,
        description='Emails associated with the user',
        examples=['foo@bar.com,other@domain.com', {'foo@bar.com', 'other@domain.com'}],
    )


@dataclass
class StoragePaths:
    """Encapsulates all storage-related paths"""

    base: Path

    @property
    def raw(self) -> Path:
        return self.base / 'raw'

    @property
    def processed(self) -> Path:
        return self.base / 'processed'

    @property
    def compact(self) -> Path:
        return self.base / 'compact'

    @property
    def entities(self) -> Path:
        return self.base / 'entities'

    def create_all(self) -> None:
        """Create all storage directories"""
        for path in [self.base, self.raw, self.processed, self.compact, self.entities]:
            path.mkdir(parents=True, exist_ok=True)


@dataclass
class AppPaths:
    """Encapsulates all application paths"""

    base: Path

    @property
    def templates(self) -> Path:
        return self.base / 'templates'

    @property
    def static(self) -> Path:
        return self.base / 'static'

    @property
    def storage(self) -> StoragePaths:
        return StoragePaths(self.base / 'storage')

    def create_all(self) -> None:
        """Create all required application directories"""
        self.templates.mkdir(parents=True, exist_ok=True)
        self.static.mkdir(parents=True, exist_ok=True)
        self.storage.create_all()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore', env_prefix='ASSISTANT_')

    # Core settings
    user_identity: UserIdentity = Field(default_factory=UserIdentity)
    host: IPvAnyAddress = Field(default='0.0.0.0')
    port: int = Field(default=8000, ge=1024, le=65535)
    app_dir: Path = Field(default=Path(__file__).parent)
    log_level: LogLevel = Field(default='info', examples=['info', 'INFO'])
    log_time_format: str = Field(default='', examples=['%x %X', '%X'])
    timezone: str = Field(default='America/Chicago')

    # Observation settings
    observation_check_interval_seconds: int = Field(default=300, ge=10, examples=[30, 120, 600])
    hl: HumanLayerSettings = Field(default_factory=HumanLayerSettings)

    @computed_field
    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @computed_field
    @property
    def paths(self) -> AppPaths:
        return AppPaths(self.app_dir)

    @model_validator(mode='after')
    def setup_logging(self) -> Self:
        # Setup logging with custom time format
        from assistant.utilities.loggers import setup_logging

        setup_logging(self.log_level, log_time_format=self.log_time_format)

        # Create directories
        self.paths.create_all()
        return self


settings = Settings()
