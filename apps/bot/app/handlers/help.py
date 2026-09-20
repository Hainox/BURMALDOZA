from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router(name="help")


async def handle_help(message: Message) -> None:
    await message.answer(
        "Команды:\n"
        "/casino — открыть игровые комнаты\n"
        "/balance — проверить подтверждённый баланс\n"
        "/top — посмотреть таблицу лидеров\n"
        "/help — показать эту справку"
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await handle_help(message)
