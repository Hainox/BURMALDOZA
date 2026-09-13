from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class BotConfig:
    token: str
    miniapp_url: str


def load_config() -> BotConfig:
    """Read runtime configuration without embedding secrets in source code."""
    token = getenv("BOT_TOKEN", "")
    miniapp_url = getenv("MINIAPP_URL", "")
    if not token or not miniapp_url:
        raise RuntimeError("BOT_TOKEN and MINIAPP_URL must be configured before the bot can start")
    return BotConfig(token=token, miniapp_url=miniapp_url)
