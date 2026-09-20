from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from ..main import BotConfig
from .casino import casino_keyboard

router = Router(name="start")


async def handle_start(message: Message, config: BotConfig) -> None:
    await message.answer(
        "Добро пожаловать в Бурмалдозу — три игровые комнаты и Jokergem без денежных операций.",
        reply_markup=casino_keyboard(config),
    )


@router.message(CommandStart())
async def start_command(message: Message, config: BotConfig) -> None:
    await handle_start(message, config)
