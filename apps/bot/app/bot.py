from __future__ import annotations

from aiogram import Bot, Dispatcher

from .api_client import BotApiClient
from .handlers import casino_router, help_router, start_router, wallet_router
from .main import BotConfig


def create_bot(config: BotConfig) -> Bot:
    return Bot(token=config.token)


def create_dispatcher(config: BotConfig) -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher["config"] = config
    dispatcher["api_client"] = BotApiClient(config.api_base_url, config.internal_api_token)
    dispatcher.include_router(start_router)
    dispatcher.include_router(help_router)
    dispatcher.include_router(casino_router)
    dispatcher.include_router(wallet_router)
    return dispatcher
