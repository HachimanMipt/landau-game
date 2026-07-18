from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_prefix="LANDAU_",
        extra="ignore",
    )

    app_name: str = "Landau Theorminimum"
    project_title_ru: str = "Теорминимум Ландау"
    environment: str = "development"
    debug: bool = False
    host: str = "127.0.0.1"
    port: int = 8000
    secret_key: str = "change-me-before-production"
    admin_password: str = "change-me"
    run_cookie_name: str = "landau_run"
    database_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'app.db').as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()

