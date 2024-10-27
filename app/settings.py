from pathlib import Path
from typing import Annotated

from humanlayer import HumanLayer
from pydantic import BeforeValidator, Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def ensure_dir(path: Path) -> Path:
    """Ensure a directory exists"""
    path.mkdir(exist_ok=True)
    return path


EnsuredPath = Annotated[Path, BeforeValidator(ensure_dir)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    # Server settings
    host: str = Field(default='0.0.0.0', alias='HOST')
    port: int = Field(default=8000, ge=1024, le=65535, alias='PORT')

    email_check_interval_seconds: int = Field(default=300, ge=10)
    observation_check_interval_seconds: int = Field(default=300, ge=10)

    app_dir: EnsuredPath = Field(default=Path(__file__).parent)

    hl: HumanLayer = Field(default=HumanLayer())

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
        for path in [self.templates_dir, self.static_dir, self.summaries_dir, self.email_credentials_dir]:
            ensure_dir(path)
        return self


settings = Settings()
