import os
from pathlib import Path
from typing import Annotated

from humanlayer import ContactChannel, HumanLayer, SlackContactChannel
from pydantic import BeforeValidator, Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def ensure_dir(path: Path) -> Path:
    """Ensure a directory exists"""
    path.mkdir(exist_ok=True)
    return path


EnsuredPath = Annotated[Path, BeforeValidator(ensure_dir)]


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

    email_check_interval_seconds: int = Field(default=300, ge=10)
    observation_check_interval_seconds: int = Field(default=300, ge=10)

    app_dir: EnsuredPath = Field(default=Path(__file__).parent)

    hl: HumanLayerSettings = Field(default_factory=HumanLayerSettings)

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


settings = Settings()
