"""Application configuration.

Settings are read from environment variables (and an optional ``.env`` file).
See ``.env.example`` for the available options.
"""
from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # .../backend


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "RRG-SCM"
    app_database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'rrg_scm.db'}"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    upload_dir: str = str(BASE_DIR / "uploads")
    default_as_of_date: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def as_of_date(self) -> date:
        if self.default_as_of_date:
            return date.fromisoformat(self.default_as_of_date)
        return date.today()

    @field_validator("app_database_url")
    @classmethod
    def _ensure_sqlite_dir(cls, v: str) -> str:
        # Make sure the SQLite file's directory exists so the engine can create it.
        prefix = "sqlite:///"
        if v.startswith(prefix):
            db_path = Path(v[len(prefix):])
            db_path.parent.mkdir(parents=True, exist_ok=True)
        return v


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    return settings
