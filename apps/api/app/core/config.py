from __future__ import annotations

import ipaddress
import re
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
    internal_api_token: str = ""
    miniapp_url: str = "https://example.invalid"
    telegram_init_data_max_age_seconds: int = 86400
    environment: str = "development"
    api_port: int = 8000


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
