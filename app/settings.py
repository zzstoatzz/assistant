import os
from pathlib import Path
from typing import Annotated, Any

from humanlayer import ContactChannel, HumanLayer, SlackContactChannel
from pydantic import BeforeValidator, Field, computed_field, model_validator
from pydantic_core import from_json
from pydantic_settings import BaseSettings, SettingsConfigDict


def ensure_dir(path: Path) -> Path:
    """Ensure a directory exists"""
    path.mkdir(exist_ok=True)
    return path


EnsuredPath = Annotated[Path, BeforeValidator(ensure_dir)]


def ensure_github_token(value: str | None) -> str:
    if not (token := value or os.getenv('GITHUB_TOKEN') or os.getenv('GH_TOKEN')):
        raise ValueError('GITHUB_TOKEN or GH_TOKEN environment variable is not set')
    return token


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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    # Server settings
    host: str = Field(default='0.0.0.0', alias='HOST')
    port: int = Field(default=8000, ge=1024, le=65535, alias='PORT')

    email_check_interval_seconds: int = Field(default=300, ge=10, alias='EMAIL_CHECK_INTERVAL_SECONDS')
    observation_check_interval_seconds: int = Field(default=300, ge=10, alias='OBSERVATION_CHECK_INTERVAL_SECONDS')

    app_dir: EnsuredPath = Field(default=Path(__file__).parent)

    hl: HumanLayerSettings = Field(default_factory=HumanLayerSettings)

    github_token: Annotated[str, BeforeValidator(ensure_github_token)]
    github_check_interval_seconds: int = Field(default=300, ge=10, alias='GITHUB_CHECK_INTERVAL_SECONDS')

    github_event_instructions: str = Field(
        default="""
        Review these GitHub notifications and create a concise summary.
        Group related items by repository and highlight anything urgent or requiring immediate attention.
        """,
        alias='GITHUB_EVENT_INSTRUCTIONS',
    )

    github_event_filters_path: Path = Field(default=f'{Path(__file__).parent}/github_event_filters.json')

    # Add new Slack settings
    slack_bot_token: str | None = Field(None, alias='SLACK_BOT_TOKEN')
    slack_check_interval_seconds: int = Field(default=300, ge=10, alias='SLACK_CHECK_INTERVAL_SECONDS')
    slack_event_instructions: str = Field(
        default="""
        Review these Slack messages and create a concise summary.
        Group related items by channel and highlight anything urgent or requiring immediate attention.
        """,
        alias='SLACK_EVENT_INSTRUCTIONS',
    )

    @computed_field
    @property
    def github_event_filters(self) -> list[dict[str, Any]]:
        """GitHub event filters"""
        if not self.github_event_filters_path.exists():
            return []
        return from_json(self.github_event_filters_path.read_bytes())

    @computed_field
    @property
    def templates_dir(self) -> Path:
        """Templates directory is inside the app directory"""
        return self.app_dir / 'templates'

    @computed_field
    @property
    def static_dir(self) -> Path:
        """Static directory is inside the app directory"""
        return self.app_dir / 'static'

    @computed_field
    @property
    def summaries_dir(self) -> Path:
        """Summaries directory is inside the app directory"""
        return self.app_dir / 'summaries'

    @computed_field
    @property
    def email_credentials_dir(self) -> Path:
        """Email credentials directory is inside the app directory"""
        return self.app_dir / 'secrets'

    @computed_field
    @property
    def processed_summaries_dir(self) -> Path:
        """Directory for processed summary files"""
        return self.summaries_dir / 'processed'

    @model_validator(mode='after')
    def ensure_paths(self):
        for path in [
            self.templates_dir,
            self.static_dir,
            self.summaries_dir,
            self.email_credentials_dir,
            self.processed_summaries_dir,
        ]:
            ensure_dir(path)
        return self

    @model_validator(mode='after')
    def debug(self):
        if f'{self.host}:{self.port}' == 'localhost:8001':
            self.log_level = 'DEBUG'
        return self


settings = Settings()  # type: ignore
