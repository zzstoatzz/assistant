from pathlib import Path

from pydantic import AnyUrl, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    # Server settings
    host: AnyUrl = Field(default='http://0.0.0.0', alias='HOST')
    port: int = Field(default=8000, ge=1024, le=65535, alias='PORT')

    @computed_field
    @property
    def app_dir(self) -> Path:
        """App directory is where this settings.py file lives"""
        return Path(__file__).parent

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

    email_check_interval_seconds: int = Field(default=300, ge=10)

    @computed_field
    @property
    def email_credentials_dir(self) -> Path:
        """Email credentials directory is inside the app directory"""
        return self.app_dir / 'secrets'


settings = Settings()
