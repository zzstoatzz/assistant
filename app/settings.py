import os
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

from humanlayer import ContactChannel, HumanLayer, SlackContactChannel
from prefect.types import LogLevel, validate_set_T_from_delim_string
from pydantic import BeforeValidator, Field, IPvAnyAddress, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self


def get_default_contact_channel() -> ContactChannel:
    if not (testing_user := os.getenv('TESTING_USER')):
        return ContactChannel()

    return ContactChannel(
        slack=SlackContactChannel(
            channel_or_user_id='',
            context_about_channel_or_user=f'a dm with {testing_user.lower()}',
            experimental_slack_blocks=True,
        )
    )


class HumanLayerSettings(BaseSettings):
    """Settings for the HumanLayer"""

    model_config = SettingsConfigDict(env_file='.env', extra='ignore', env_prefix='HUMANLAYER_')

    api_key: str | None = Field(default=None, description='HumanLayer API key')
    slack: ContactChannel | None = Field(default_factory=get_default_contact_channel)

    @computed_field
    @property
    def instance(self) -> HumanLayer:
        """HumanLayer instance"""
        return HumanLayer(api_key=self.api_key, contact_channel=self.slack)


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


Activation = Annotated[float, Field(ge=0.0, le=1.0)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore', env_prefix='ASSISTANT_')

    # Core settings
    user_identity: UserIdentity = Field(default_factory=UserIdentity)
    timezone: str = Field(default='America/Chicago')

    host: IPvAnyAddress = Field(default='0.0.0.0')
    port: int = Field(default=8000, ge=1024, le=65535)
    app_dir: Path = Field(default=Path(__file__).parent)

    log_level: LogLevel = Field(default='info', examples=['info', 'INFO'])
    log_time_format: str | None = Field(default=None, examples=['%x %X', '%X'])

    # Observation settings
    observation_check_interval_seconds: int = Field(default=300, ge=10, examples=[30, 120, 600])
    observation_initial_delay_seconds: int = Field(
        default=30,
        gt=0,
        description='Initial delay before first compression check',
        examples=[30, 60, 120],
    )
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
        from assistant.utilities.loggers import setup_logging

        setup_logging(self.log_level, log_time_format=self.log_time_format)

        self.paths.create_all()
        return self

    # Storage limits and thresholds
    max_unprocessed_batch_size: int = Field(
        default=50,
        gt=0,
        description='Maximum number of raw summaries to process in one batch',
        examples=[25, 50, 100],
    )
    max_context_entities: int = Field(
        default=100,
        gt=0,
        description='Maximum number of entities to use for context',
        examples=[50, 100, 200],
    )
    max_historical_pins: int = Field(
        default=10,
        gt=0,
        description='Maximum number of historical pins to use for context',
        examples=[5, 10, 20],
    )

    # Importance thresholds
    entity_importance_threshold: Activation = Field(
        default=0.5,
        description='Minimum importance score to keep an entity',
        examples=[0.3, 0.5, 0.7],
    )
    historical_pin_threshold: Activation = Field(
        default=0.7,
        description='Minimum importance score to create historical pin',
        examples=[0.5, 0.7, 0.9],
    )
    context_entity_threshold: Activation = Field(
        default=0.7,
        description='Minimum importance score for entities used in historical context',
        examples=[0.5, 0.7, 0.9],
    )


settings = Settings()
