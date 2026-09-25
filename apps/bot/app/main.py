from __future__ import annotations

import asyncio
from dataclasses import dataclass
from os import getenv
from urllib.parse import urlparse


@dataclass(frozen=True)
class BotConfig:
    token: str
    internal_api_token: str
    miniapp_url: str
    api_base_url: str
    environment: str = "development"

    def __post_init__(self) -> None:
        if not self.token:
            raise RuntimeError("BOT_TOKEN must be configured")
        if (
            not self.internal_api_token
            or not self.internal_api_token.isascii()
            or not self.internal_api_token.isprintable()
            or any(character.isspace() for character in self.internal_api_token)
            or self.internal_api_token == self.token
        ):
            raise RuntimeError("INTERNAL_API_TOKEN must be configured separately from BOT_TOKEN")
        _validate_url("MINIAPP_URL", self.miniapp_url, self.environment)
        _validate_url("API_BASE_URL", self.api_base_url, self.environment)


def _validate_url(name: str, value: str, environment: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError(f"{name} must be an absolute http(s) URL")
    if environment == "production":
        if parsed.scheme != "https":
            raise RuntimeError(f"{name} must use HTTPS in production")
        if parsed.hostname in {"example.invalid", "localhost", "127.0.0.1"}:
            raise RuntimeError(f"{name} must point to a real production host")


def load_config() -> BotConfig:
    """Read runtime configuration without embedding secrets in source code."""
    token = getenv("BOT_TOKEN", "")
    internal_api_token = getenv("INTERNAL_API_TOKEN", "")
    miniapp_url = getenv("MINIAPP_URL", "")
    api_base_url = getenv("API_BASE_URL", "")
    environment = getenv("ENVIRONMENT", "development").lower()
    missing = [
        name
        for name, value in (
            ("BOT_TOKEN", token),
            ("INTERNAL_API_TOKEN", internal_api_token),
            ("MINIAPP_URL", miniapp_url),
            ("API_BASE_URL", api_base_url),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(f"{', '.join(missing)} must be configured before the bot can start")
    return BotConfig(
        token=token,
        internal_api_token=internal_api_token,
        miniapp_url=miniapp_url,
        api_base_url=api_base_url,
        environment=environment,
    )


async def run() -> None:
    from .bot import create_bot, create_dispatcher

    config = load_config()
    bot = create_bot(config)
    dispatcher = create_dispatcher(config)
    api_client = dispatcher["api_client"]
    try:
        await dispatcher.start_polling(bot)
    finally:
        await api_client.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(run())
