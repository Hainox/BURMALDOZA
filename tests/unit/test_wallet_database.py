from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import Settings
from app.db.models import Base, LedgerEntry, User, Wallet
from app.dependencies import authenticate_raw_init_data
from app.services.room_service import RoomService
from app.services.wallet_service import WalletService, WalletServiceError
from burmaldoza_contracts.rooms import WebSocketAuthMessage
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tests.unit.test_telegram_auth import BOT_TOKEN, make_init_data


@pytest.mark.asyncio
async def test_missing_user_does_not_create_a_wallet_or_placeholder_user() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    try:
        async with session_factory() as session:
            with pytest.raises(WalletServiceError, match="user not found"):
                await WalletService(session).get_or_create(42)

        async with session_factory() as session:
            assert await session.scalar(select(func.count()).select_from(User)) == 0
            assert await session.scalar(select(func.count()).select_from(Wallet)) == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_first_login_creates_one_user_and_one_welcome(tmp_path) -> None:
    database_path = tmp_path / "first-login.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_path.as_posix()}", connect_args={"timeout": 10}
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.exec_driver_sql("PRAGMA journal_mode=WAL")
        await connection.run_sync(Base.metadata.create_all)

    raw = make_init_data(
        auth_date=datetime.now(UTC) - timedelta(minutes=5),
        user={"id": 30042, "first_name": "Player"},
    )
    settings = Settings(bot_token=BOT_TOKEN)
    start = asyncio.Event()

    async def login():
        async with session_factory() as session:
            await start.wait()
            return await authenticate_raw_init_data(raw, session, settings)

    try:
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
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("protocols", [("http", "websocket"), ("websocket", "websocket")])
async def test_concurrent_websocket_login_shares_one_welcome(tmp_path, protocols) -> None:
    database_path = tmp_path / "mixed-login.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_path.as_posix()}", connect_args={"timeout": 10}
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.exec_driver_sql("PRAGMA journal_mode=WAL")
        await connection.run_sync(Base.metadata.create_all)

    now = datetime.now(UTC)
    raw = make_init_data(
        auth_date=now - timedelta(minutes=5),
        user={"id": 30044, "first_name": "Player"},
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

    try:
        login = {"http": http_login, "websocket": websocket_login}
        attempts = [asyncio.create_task(login[protocol]()) for protocol in protocols]
        start.set()
        first, second = await asyncio.gather(*attempts)

        assert first.user_id == second.user_id
        async with session_factory() as session:
            assert await session.scalar(select(func.count()).select_from(User)) == 1
            assert await session.scalar(select(func.count()).select_from(Wallet)) == 1
            assert await session.scalar(select(func.count()).select_from(LedgerEntry)) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_wallet_creation_for_existing_user_is_idempotent(tmp_path) -> None:
    database_path = tmp_path / "wallet-create.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_path.as_posix()}", connect_args={"timeout": 10}
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.exec_driver_sql("PRAGMA journal_mode=WAL")
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session, session.begin():
        session.add(User(telegram_user_id=30043, display_name="Existing Player"))
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.telegram_user_id == 30043))
        assert user is not None
        user_id = user.id

    start = asyncio.Event()

    async def read_wallet():
        async with session_factory() as session:
            await start.wait()
            return await WalletService(session).get_or_create(user_id)

    try:
        attempts = [asyncio.create_task(read_wallet()) for _ in range(2)]
        start.set()
        first, second = await asyncio.gather(*attempts)

        assert first == second
        assert first.balance == 0
        async with session_factory() as session:
            assert await session.scalar(select(func.count()).select_from(Wallet)) == 1
    finally:
        await engine.dispose()
