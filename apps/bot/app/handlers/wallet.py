from __future__ import annotations

from typing import Any

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from ..api_client import BotApiClient, BotApiError
from ..main import BotConfig
from .casino import casino_keyboard

router = Router(name="wallet")


def _telegram_user_id(message: Message) -> int | None:
    return message.from_user.id if message.from_user is not None else None


async def handle_balance(message: Message, config: BotConfig, api_client: BotApiClient) -> None:
    user_id = _telegram_user_id(message)
    if user_id is None:
        await message.answer("Не удалось определить Telegram-пользователя.")
        return
    try:
        payload = await api_client.get_balance(user_id)
    except BotApiError:
        await message.answer("Баланс временно недоступен. Откройте Mini App для повторной попытки.")
        return
    balance = int(payload.get("balance", 0))
    currency = str(payload.get("currency_code", "JOKERGEM"))
    await message.answer(f"Ваш баланс: {balance:,} {currency}".replace(",", " "))


async def handle_top(message: Message, config: BotConfig, api_client: BotApiClient) -> None:
    try:
        rows: list[dict[str, Any]] = await api_client.get_top()
    except BotApiError:
        await message.answer("Таблица лидеров временно недоступна.")
        return
    if not rows:
        await message.answer("Таблица лидеров пока пуста.")
        return
    lines = [
        f"{index}. {row.get('display_name', 'Игрок')} — {int(row.get('balance', 0)):,} JOKERGEM".replace(
            ",", " "
        )
        for index, row in enumerate(rows[:10], start=1)
    ]
    await message.answer("Топ игроков:\n" + "\n".join(lines), reply_markup=casino_keyboard(config))


@router.message(Command("balance"))
async def balance_command(message: Message, config: BotConfig, api_client: BotApiClient) -> None:
    await handle_balance(message, config, api_client)


@router.message(Command("top"))
async def top_command(message: Message, config: BotConfig, api_client: BotApiClient) -> None:
    await handle_top(message, config, api_client)
