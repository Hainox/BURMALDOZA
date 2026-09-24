import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.core.config import Settings
from app.db.models import LedgerEntry, User, Wallet
from app.dependencies import authenticate_raw_init_data
from app.services.room_service import RoomService
from app.services.wallet_service import WalletService
from burmaldoza_contracts.rooms import WebSocketAuthMessage
from burmaldoza_domain.core import InsufficientBalanceError
from burmaldoza_domain.economy import LedgerReason
from sqlalchemy import func, select

from tests.unit.test_telegram_auth import BOT_TOKEN, make_init_data


@pytest.mark.asyncio
async def test_concurrent_first_login_grants_welcome_once(session_factory) -> None:
    raw = make_init_data(
        auth_date=datetime.now(UTC) - timedelta(minutes=5),
        user={"id": 40042, "first_name": "Player"},
    )
    settings = Settings(bot_token=BOT_TOKEN)
    start = asyncio.Event()

    async def login():
        async with session_factory() as session:
            await start.wait()
            return await authenticate_raw_init_data(raw, session, settings)

    attempts = [asyncio.create_task(login()) for _ in range(2)]
    start.set()
    first, second = await asyncio.gather(*attempts)

    assert first.user_id == second.user_id
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(User)) == 1
        assert await session.scalar(select(func.count()).select_from(Wallet)) == 1
        assert await session.scalar(select(func.count()).select_from(LedgerEntry)) == 1
        wallet = await session.get(Wallet, first.user_id)
        assert wallet is not None
        assert wallet.balance == 1000
        assert wallet.welcome_granted_at is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("protocols", [("http", "websocket"), ("websocket", "websocket")])
async def test_concurrent_websocket_login_grants_welcome_once(session_factory, protocols) -> None:
    now = datetime.now(UTC)
    raw = make_init_data(
        auth_date=now - timedelta(minutes=5),
        user={"id": 40043, "first_name": "Player"},
    )
    settings = Settings(bot_token=BOT_TOKEN)
    start = asyncio.Event()

    async def http_login():
        async with session_factory() as session:
            await start.wait()
            return await authenticate_raw_init_data(raw, session, settings)

    async def websocket_login():
        async with session_factory() as session:
            service = RoomService(session=session, bot_token=BOT_TOKEN, now=lambda: now)
            await start.wait()
            return await service.authenticate_websocket(
                WebSocketAuthMessage(type="auth", init_data=raw)
            )

    login = {"http": http_login, "websocket": websocket_login}
    attempts = [asyncio.create_task(login[protocol]()) for protocol in protocols]
    start.set()
    first, second = await asyncio.gather(*attempts)

    assert first.user_id == second.user_id
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(User)) == 1
        assert await session.scalar(select(func.count()).select_from(Wallet)) == 1
        assert await session.scalar(select(func.count()).select_from(LedgerEntry)) == 1


@pytest.mark.asyncio
async def test_concurrent_spends_never_make_balance_negative(session_factory) -> None:
    async with session_factory() as session:
        session.add(User(id=202, telegram_user_id=202, display_name="Wallet User"))
        await session.commit()
        service = WalletService(session)
        await service.apply_delta(202, 100, LedgerReason.WELCOME, uuid4(), uuid4())

    async def spend() -> object:
        async with session_factory() as session:
            try:
                return await WalletService(session).apply_delta(
                    202, -80, LedgerReason.GAME_STAKE, uuid4(), uuid4()
                )
            except InsufficientBalanceError as error:
                return error

    results = await asyncio.gather(spend(), spend())
    assert sum(not isinstance(result, InsufficientBalanceError) for result in results) == 1

    async with session_factory() as session:
        wallet = await session.scalar(select(Wallet).where(Wallet.user_id == 202))
        assert wallet is not None
        assert wallet.balance == 20
        assert wallet.balance >= 0
