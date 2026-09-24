from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from apps.bot.app.handlers.casino import casino_keyboard, handle_casino
from apps.bot.app.handlers.help import handle_help
from apps.bot.app.handlers.start import handle_start
from apps.bot.app.handlers.wallet import handle_balance, handle_top
from apps.bot.app.main import BotConfig


@pytest.fixture
def config() -> BotConfig:
    return BotConfig(
        token="TEST_BOT_TOKEN",
        internal_api_token="TEST_INTERNAL_TOKEN",
        miniapp_url="https://miniapp.example.test",
        api_base_url="https://api.example.test",
        environment="test",
    )


@pytest.mark.asyncio
async def test_start_and_casino_return_mini_app_launch_surface(config: BotConfig) -> None:
    message = SimpleNamespace(answer=AsyncMock())

    await handle_start(message, config)
    await handle_casino(message, config)

    assert message.answer.await_count == 2
    keyboard = casino_keyboard(config)
    assert keyboard.inline_keyboard[0][0].web_app.url == config.miniapp_url


@pytest.mark.asyncio
async def test_help_is_explicit_and_does_not_send_unsolicited_messages() -> None:
    message = SimpleNamespace(answer=AsyncMock())

    await handle_help(message)

    message.answer.assert_awaited_once()
    assert "/casino" in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_balance_uses_api_result_and_top_uses_api_rows(config: BotConfig) -> None:
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=42),
        answer=AsyncMock(),
    )
    api_client = SimpleNamespace(
        get_balance=AsyncMock(return_value={"balance": 1250, "currency_code": "JOKERGEM"}),
        get_top=AsyncMock(return_value=[{"display_name": "Ada", "balance": 1250}]),
    )

    await handle_balance(message, config, api_client)
    await handle_top(message, config, api_client)

    api_client.get_balance.assert_awaited_once_with(42)
    api_client.get_top.assert_awaited_once()
    assert "1 250" in message.answer.await_args_list[0].args[0]
    assert "Ada" in message.answer.await_args_list[1].args[0]
