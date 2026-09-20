from __future__ import annotations

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


settings = Settings()
