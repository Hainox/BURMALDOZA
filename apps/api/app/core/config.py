from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit

from burmaldoza_domain.games.slot_operations import OperationOverride
from pydantic import AwareDatetime, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True
    )

    database_url: str = Field(
        default="postgresql+asyncpg://burmaldoza:change-me-before-local-run@localhost:5432/burmaldoza"
    )
    redis_url: str = "redis://localhost:6379/0"
    bot_token: str = ""
    internal_api_token: str = ""
    miniapp_url: str = "https://example.invalid"
    telegram_init_data_max_age_seconds: int = 86400
    environment: str = "development"
    api_port: int = 8000
    # Telegram ID админов бота через запятую (только в .env сервера, не в репозитории).
    admin_telegram_ids: str = ""
    slot_event_operation_id: str | None = None
    slot_event_starts_at: AwareDatetime | None = None
    slot_event_ends_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_slot_event(self) -> Settings:
        _ = self.admin_ids  # опечатка в ADMIN_TELEGRAM_IDS — ошибка при старте, а не 500 на команде
        fields = (self.slot_event_operation_id, self.slot_event_starts_at, self.slot_event_ends_at)
        if any(value is not None for value in fields):
            if any(value is None for value in fields):
                raise ValueError("slot event requires operation ID, start and end together")
            _ = self.slot_operation_override
        return self

    @property
    def admin_ids(self) -> frozenset[int]:
        ids: set[int] = set()
        for part in self.admin_telegram_ids.replace(";", ",").split(","):
            part = part.strip()
            if part:
                if not part.isdigit():
                    raise ValueError("ADMIN_TELEGRAM_IDS must be comma-separated Telegram user IDs")
                ids.add(int(part))
        return frozenset(ids)

    @property
    def slot_operation_override(self) -> OperationOverride | None:
        if self.slot_event_operation_id is None:
            return None
        assert self.slot_event_starts_at is not None and self.slot_event_ends_at is not None
        return OperationOverride(
            self.slot_event_operation_id, self.slot_event_starts_at, self.slot_event_ends_at
        )


_DEFAULT_PORTS = {"http": 80, "https": 443}
# ASCII DNS name (IDN hosts must be given in punycode, as browsers send them).
_HOSTNAME_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*")


def _origin_host(hostname: str) -> str | None:
    if ":" in hostname:
        try:
            address = ipaddress.IPv6Address(hostname)
        except ValueError:
            return None
        # Browsers never send a zone id in Origin.
        return None if address.scope_id else f"[{address.compressed}]"
    return hostname if _HOSTNAME_PATTERN.fullmatch(hostname) else None


def cors_origin(url: str) -> str | None:
    """Return the browser Origin (scheme://host[:port]) for a Mini App URL.

    MINIAPP_URL may carry a path (GitHub Pages: https://host/REPO/), but browsers
    send Origin without it and in canonical form (lowercase host, no default port),
    so the raw URL would never match. Malformed URLs and URLs with userinfo are
    rejected (None) rather than guessed.
    """
    try:
        parsed = urlsplit(url.strip())
        port = parsed.port
    except ValueError:
        return None
    default_port = _DEFAULT_PORTS.get(parsed.scheme)
    if default_port is None or "@" in parsed.netloc or not parsed.hostname:
        return None
    host = _origin_host(parsed.hostname)
    if host is None:
        return None
    if port is None or port == default_port:
        return f"{parsed.scheme}://{host}"
    return f"{parsed.scheme}://{host}:{port}"


settings = Settings()
