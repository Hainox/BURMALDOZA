from __future__ import annotations

from urllib.parse import urlsplit

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(
        default="postgresql+asyncpg://burmaldoza:change-me-before-local-run@localhost:5432/burmaldoza"
    )
    redis_url: str = "redis://localhost:6379/0"
    bot_token: str = ""
    miniapp_url: str = "https://example.invalid"
    telegram_init_data_max_age_seconds: int = 86400
    environment: str = "development"
    api_port: int = 8000


def cors_origin(url: str) -> str | None:
    """Return the browser Origin (scheme://host[:port]) for a Mini App URL.

    MINIAPP_URL may carry a path (GitHub Pages: https://host/REPO/), but browsers
    send Origin without it, so the raw URL would never match.
    """
    parsed = urlsplit(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


settings = Settings()
