from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from apps.bot.app.api_client import BotApiError
from apps.bot.app.handlers import admin
from apps.bot.app.main import BotConfig, parse_admin_ids

ADMIN = 1001


@pytest.fixture
def config() -> BotConfig:
    return BotConfig(
        token="TEST_BOT_TOKEN",
        internal_api_token="TEST_INTERNAL_TOKEN",
        miniapp_url="https://miniapp.example.test",
        api_base_url="https://api.example.test",
        environment="test",
        admin_telegram_ids=frozenset({ADMIN}),
    )


@pytest.fixture(autouse=True)
def clear_pending():
    admin._pending.clear()
    yield
    admin._pending.clear()


def message(user_id: int, chat_type: str = "private") -> SimpleNamespace:
    return SimpleNamespace(
        from_user=SimpleNamespace(id=user_id, is_bot=False),
        chat=SimpleNamespace(type=chat_type),
        reply_to_message=None,
        answer=AsyncMock(),
    )


def command(name: str, args: str | None) -> SimpleNamespace:
    return SimpleNamespace(command=name, args=args)


def target(balance: int = 1250) -> dict:
    return {
        "telegram_user_id": 2002,
        "display_name": "Player",
        "username": "lucky",
        "balance": balance,
    }


def test_admin_ids_parse_and_reject_typos() -> None:
    assert parse_admin_ids(" 1, 22;333 ") == frozenset({1, 22, 333})
    assert parse_admin_ids("") == frozenset()
    with pytest.raises(RuntimeError):
        parse_admin_ids("12,abc")


@pytest.mark.asyncio
async def test_non_admins_and_group_chats_get_silence(config: BotConfig) -> None:
    api = SimpleNamespace(admin_lookup=AsyncMock())
    for msg in (message(42), message(ADMIN, chat_type="supergroup")):
        await admin.handle_admin_help(msg, config)
        await admin.handle_adjust(msg, command("give", "@lucky 500"), config, api, 1)
        msg.answer.assert_not_awaited()
    api.admin_lookup.assert_not_awaited()


@pytest.mark.asyncio
async def test_give_shows_confirmation_and_confirm_uses_one_key(config: BotConfig) -> None:
    api = SimpleNamespace(
        admin_lookup=AsyncMock(return_value=target()),
        admin_adjust=AsyncMock(
            return_value={"balance_before": 1250, "balance_after": 1750, "replayed": False}
        ),
    )
    msg = message(ADMIN)
    await admin.handle_adjust(msg, command("give", "@lucky 500 приз"), config, api, 1)
    text = msg.answer.await_args.args[0]
    assert "Начислить 500 JG — @lucky?" in text and "1 250 → 1 750" in text
    keyboard = msg.answer.await_args.kwargs["reply_markup"].inline_keyboard[0]
    confirm = keyboard[0].callback_data

    stranger = SimpleNamespace(data=confirm, from_user=SimpleNamespace(id=42), answer=AsyncMock())
    await admin.handle_confirmation(stranger, config, api)
    api.admin_adjust.assert_not_awaited()

    callback = SimpleNamespace(
        data=confirm,
        from_user=SimpleNamespace(id=ADMIN),
        answer=AsyncMock(),
        message=SimpleNamespace(edit_text=AsyncMock(), answer=AsyncMock()),
        bot=SimpleNamespace(send_message=AsyncMock()),
    )
    await admin.handle_confirmation(callback, config, api)
    actor, player, delta, comment, _key = api.admin_adjust.await_args.args
    assert (actor, player, delta, comment) == (ADMIN, 2002, 500, "приз")
    assert "1 250 → 1 750" in callback.message.edit_text.await_args.args[0]
    callback.bot.send_message.assert_awaited_once()
    assert callback.bot.send_message.await_args.args[0] == 2002


@pytest.mark.asyncio
async def test_failed_confirm_keeps_the_same_key_for_a_safe_retry(config: BotConfig) -> None:
    api = SimpleNamespace(
        admin_lookup=AsyncMock(return_value=target()),
        admin_adjust=AsyncMock(
            side_effect=[
                BotApiError("down"),
                {"balance_before": 1250, "balance_after": 1750, "replayed": True},
            ]
        ),
    )
    msg = message(ADMIN)
    await admin.handle_adjust(msg, command("give", "@lucky 500"), config, api, 1)
    data = msg.answer.await_args.kwargs["reply_markup"].inline_keyboard[0][0].callback_data
    callback = SimpleNamespace(
        data=data,
        from_user=SimpleNamespace(id=ADMIN),
        answer=AsyncMock(),
        message=SimpleNamespace(edit_text=AsyncMock(), answer=AsyncMock()),
        bot=SimpleNamespace(send_message=AsyncMock()),
    )
    await admin.handle_confirmation(callback, config, api)
    await admin.handle_confirmation(callback, config, api)
    keys = [call.args[4] for call in api.admin_adjust.await_args_list]
    assert len(keys) == 2 and keys[0] == keys[1]
    # первый ответ потерялся — игрок всё равно получает ровно одно уведомление после успешного повтора
    callback.bot.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_take_below_zero_and_bad_amounts_are_refused_before_confirmation(
    config: BotConfig,
) -> None:
    api = SimpleNamespace(admin_lookup=AsyncMock(return_value=target(balance=100)))
    msg = message(ADMIN)
    await admin.handle_adjust(msg, command("take", "@lucky 500"), config, api, -1)
    assert "списать 500 нельзя" in msg.answer.await_args.args[0]
    for bad in ("0", "-5", "abc", "1000001"):
        await admin.handle_adjust(msg, command("give", f"@lucky {bad}"), config, api, 1)
        assert "Сумма — целое число" in msg.answer.await_args.args[0]
    assert admin._pending == {}


@pytest.mark.asyncio
async def test_reply_to_forwarded_message_targets_the_original_author(config: BotConfig) -> None:
    api = SimpleNamespace(admin_lookup=AsyncMock(return_value=target()))
    msg = message(ADMIN)
    msg.reply_to_message = SimpleNamespace(
        forward_origin=SimpleNamespace(sender_user=SimpleNamespace(id=2002, is_bot=False)),
        from_user=SimpleNamespace(id=ADMIN, is_bot=False),
    )
    await admin.handle_adjust(msg, command("give", "500"), config, api, 1)
    assert api.admin_lookup.await_args.args == (ADMIN, "2002")

    hidden = message(ADMIN)
    hidden.reply_to_message = SimpleNamespace(
        forward_origin=SimpleNamespace(sender_user_name="Скрыт"), from_user=None
    )
    await admin.handle_adjust(hidden, command("give", "500"), config, api, 1)
    assert "скрыл аккаунт" in hidden.answer.await_args.args[0]
    assert api.admin_lookup.await_count == 1


@pytest.mark.asyncio
async def test_long_comment_is_refused_before_confirmation(config: BotConfig) -> None:
    api = SimpleNamespace(admin_lookup=AsyncMock(return_value=target()))
    msg = message(ADMIN)
    await admin.handle_adjust(msg, command("give", "@lucky 500 " + "x" * 201), config, api, 1)
    assert "длиннее 200" in msg.answer.await_args.args[0]
    api.admin_lookup.assert_not_awaited()
    assert admin._pending == {}


@pytest.mark.asyncio
async def test_second_tap_while_request_is_in_flight_does_nothing(config: BotConfig) -> None:
    api = SimpleNamespace(admin_lookup=AsyncMock(return_value=target()), admin_adjust=AsyncMock())
    msg = message(ADMIN)
    await admin.handle_adjust(msg, command("give", "@lucky 500"), config, api, 1)
    data = msg.answer.await_args.kwargs["reply_markup"].inline_keyboard[0][0].callback_data
    admin._inflight.add(data.split(":")[2])
    callback = SimpleNamespace(data=data, from_user=SimpleNamespace(id=ADMIN), answer=AsyncMock())
    await admin.handle_confirmation(callback, config, api)
    api.admin_adjust.assert_not_awaited()
    assert callback.answer.await_args.args[0] == "Выполняется…"
    admin._inflight.clear()
