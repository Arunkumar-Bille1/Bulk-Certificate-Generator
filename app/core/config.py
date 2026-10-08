"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    APP_NAME: str = "Bulk Certificate Generator"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/certificate_db"

    # Certificate storage
    CERTIFICATES_DIR: str = "certificates"

    # Limits
    MAX_RECIPIENTS_PER_JOB: int = 500

    @property
    def certificates_path(self) -> Path:
        path = Path(self.CERTIFICATES_DIR)
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
