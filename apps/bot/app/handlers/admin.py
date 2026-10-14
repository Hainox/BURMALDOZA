"""Админ-команды бота: /admin, /bal, /give, /take.

Работают только в личке с ботом и только у Telegram ID из ADMIN_TELEGRAM_IDS (остальным бот молчит,
чтобы не раскрывать команды). Деньги меняет сервер; перед начислением — карточка подтверждения,
кнопки которой может нажать только тот же админ. Ключ идемпотентности создаётся при показе карточки,
поэтому повторное «Подтвердить» не начислит дважды.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from ..api_client import BotApiClient, BotApiError
from ..main import BotConfig

router = Router(name="admin")

MAX_AMOUNT = 1_000_000
PENDING_TTL_SECONDS = 300

HELP = (
    "Админ-команды (только здесь, в личке):\n"
    "/bal @ник — баланс игрока\n"
    "/give @ник 500 [комментарий] — начислить JG\n"
    "/take @ник 500 [комментарий] — списать JG (не ниже нуля)\n"
    "Можно ответом на сообщение игрока: /give 500\n"
    f"Не больше {MAX_AMOUNT:,} JG за операцию; перед изменением — подтверждение.".replace(",", " ")
)


@dataclass(frozen=True)
class PendingAdjustment:
    actor: int
    target: int
    target_label: str
    delta: int
    comment: str
    key: str
    created: float


# Ожидающие подтверждения операции (в памяти процесса бота, живут 5 минут).
_pending: dict[str, PendingAdjustment] = {}


def _fmt(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def _is_admin_chat(message: Message, config: BotConfig) -> bool:
    user = message.from_user
    return (
        user is not None and user.id in config.admin_telegram_ids and message.chat.type == "private"
    )


def _label(target: dict) -> str:
    username = target.get("username")
    name = str(target.get("display_name") or target.get("telegram_user_id"))
    return f"@{username}" if username else name


def _parse_amount(text: str) -> int | None:
    cleaned = text.replace(" ", "").replace("_", "")
    if not cleaned.isdigit():
        return None
    value = int(cleaned)
    return value if 0 < value <= MAX_AMOUNT else None


def _target_and_rest(message: Message, command: CommandObject) -> tuple[str | None, list[str]]:
    args = (command.args or "").split()
    reply = message.reply_to_message
    if reply is not None and reply.from_user is not None and not reply.from_user.is_bot:
        return str(reply.from_user.id), args
    if not args:
        return None, []
    return args[0], args[1:]


async def _lookup(message: Message, api_client: BotApiClient, query: str) -> dict | None:
    try:
        return await api_client.admin_lookup(message.from_user.id, query)
    except BotApiError as error:
        if error.status == 404:
            await message.answer("Игрок не найден. Он должен хотя бы раз открыть Mini App.")
        elif error.status == 403:
            await message.answer("Сервер не подтвердил права администратора.")
        else:
            await message.answer("Сервер недоступен, попробуйте позже.")
        return None


async def handle_admin_help(message: Message, config: BotConfig) -> None:
    if _is_admin_chat(message, config):
        await message.answer(HELP)


async def handle_admin_balance(
    message: Message, command: CommandObject, config: BotConfig, api_client: BotApiClient
) -> None:
    if not _is_admin_chat(message, config):
        return
    query, _ = _target_and_rest(message, command)
    if query is None:
        await message.answer("Укажите игрока: /bal @ник")
        return
    target = await _lookup(message, api_client, query)
    if target:
        await message.answer(f"{_label(target)}: {_fmt(int(target['balance']))} JG")


async def handle_adjust(
    message: Message, command: CommandObject, config: BotConfig, api_client: BotApiClient, sign: int
) -> None:
    if not _is_admin_chat(message, config):
        return
    query, rest = _target_and_rest(message, command)
    usage = f"Формат: /{command.command} @ник 500 [комментарий]"
    if query is None or not rest:
        await message.answer(usage)
        return
    amount = _parse_amount(rest[0])
    if amount is None:
        await message.answer(f"Сумма — целое число от 1 до {_fmt(MAX_AMOUNT)}. {usage}")
        return
    target = await _lookup(message, api_client, query)
    if not target:
        return
    delta = sign * amount
    balance = int(target["balance"])
    if balance + delta < 0:
        await message.answer(
            f"У {_label(target)} только {_fmt(balance)} JG — списать {_fmt(amount)} нельзя."
        )
        return
    _drop_expired()
    token = uuid.uuid4().hex[:12]
    _pending[token] = PendingAdjustment(
        actor=message.from_user.id,
        target=int(target["telegram_user_id"]),
        target_label=_label(target),
        delta=delta,
        comment=" ".join(rest[1:]),
        key=str(uuid.uuid4()),
        created=time.monotonic(),
    )
    verb = "Начислить" if delta > 0 else "Списать"
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Подтвердить", callback_data=f"adm:ok:{token}"),
                InlineKeyboardButton(text="Отмена", callback_data=f"adm:no:{token}"),
            ]
        ]
    )
    comment = f"\nКомментарий: {_pending[token].comment}" if _pending[token].comment else ""
    await message.answer(
        f"{verb} {_fmt(amount)} JG — {_label(target)}?\nБаланс: {_fmt(balance)} → {_fmt(balance + delta)} JG{comment}",
        reply_markup=keyboard,
    )


def _drop_expired() -> None:
    now = time.monotonic()
    for token in [t for t, p in _pending.items() if now - p.created > PENDING_TTL_SECONDS]:
        _pending.pop(token, None)


async def handle_confirmation(
    callback: CallbackQuery, config: BotConfig, api_client: BotApiClient
) -> None:
    _, action, token = (callback.data or "adm::").split(":", 2)
    pending = _pending.get(token)
    user_id = callback.from_user.id if callback.from_user else None
    if user_id not in config.admin_telegram_ids or (
        pending is not None and pending.actor != user_id
    ):
        await callback.answer("Это подтверждение не для вас.", show_alert=True)
        return
    if pending is None or time.monotonic() - pending.created > PENDING_TTL_SECONDS:
        _pending.pop(token, None)
        await callback.answer("Подтверждение устарело — повторите команду.", show_alert=True)
        return
    if action == "no":
        _pending.pop(token, None)
        await callback.message.edit_text("Отменено, баланс не менялся.")
        await callback.answer()
        return
    try:
        result = await api_client.admin_adjust(
            pending.actor, pending.target, pending.delta, pending.comment, pending.key
        )
    except BotApiError as error:
        reason = {
            409: "недостаточно средств",
            403: "нет прав",
            404: "игрок не найден",
            422: "неверная сумма",
        }.get(
            error.status or 0,
            "сервер недоступен — нажмите «Подтвердить» ещё раз, повторного списания не будет",
        )
        await callback.answer(f"Не выполнено: {reason}", show_alert=True)
        return
    _pending.pop(token, None)
    done = "Начислено" if pending.delta > 0 else "Списано"
    await callback.message.edit_text(
        f"{done} {_fmt(abs(pending.delta))} JG — {pending.target_label}.\n"
        f"Баланс: {_fmt(int(result['balance_before']))} → {_fmt(int(result['balance_after']))} JG"
    )
    await callback.answer("Готово")
    if not result.get("replayed"):
        verb = "начислил вам" if pending.delta > 0 else "списал у вас"
        comment = f"\nКомментарий: {pending.comment}" if pending.comment else ""
        try:
            await callback.bot.send_message(
                pending.target,
                f"Администратор {verb} {_fmt(abs(pending.delta))} JG. Баланс: {_fmt(int(result['balance_after']))} JG{comment}",
            )
        except Exception:  # noqa: BLE001 — игрок мог закрыть личку с ботом; начисление уже проведено
            await callback.message.answer(
                "Уведомление игроку не доставлено (личка с ботом закрыта)."
            )


@router.message(Command("admin"))
async def admin_command(message: Message, config: BotConfig) -> None:
    await handle_admin_help(message, config)


@router.message(Command("bal"))
async def bal_command(
    message: Message, command: CommandObject, config: BotConfig, api_client: BotApiClient
) -> None:
    await handle_admin_balance(message, command, config, api_client)


@router.message(Command("give"))
async def give_command(
    message: Message, command: CommandObject, config: BotConfig, api_client: BotApiClient
) -> None:
    await handle_adjust(message, command, config, api_client, 1)


@router.message(Command("take"))
async def take_command(
    message: Message, command: CommandObject, config: BotConfig, api_client: BotApiClient
) -> None:
    await handle_adjust(message, command, config, api_client, -1)


@router.callback_query(F.data.startswith("adm:"))
async def confirmation_callback(
    callback: CallbackQuery, config: BotConfig, api_client: BotApiClient
) -> None:
    await handle_confirmation(callback, config, api_client)
