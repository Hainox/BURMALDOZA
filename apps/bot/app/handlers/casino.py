from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from ..main import BotConfig

router = Router(name="casino")


def casino_keyboard(config: BotConfig) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎲 Открыть Бурмалдозу",
                    web_app=WebAppInfo(url=config.miniapp_url),
                )
            ]
        ]
    )


async def handle_casino(message: Message, config: BotConfig) -> None:
    await message.answer(
        "Игровые комнаты открываются в Mini App. Результаты и баланс подтверждает сервер.",
        reply_markup=casino_keyboard(config),
    )


@router.message(Command("casino"))
async def casino_command(message: Message, config: BotConfig) -> None:
    await handle_casino(message, config)
