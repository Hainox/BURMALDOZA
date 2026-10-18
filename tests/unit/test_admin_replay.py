"""Real database replay checks; CI uses PostgreSQL, local fallback uses SQLite."""
from __future__ import annotations

import os
from uuid import uuid4

import pytest
import pytest_asyncio
from app.db.models import AdminAuditLog, Base, LedgerEntry, User, Wallet
from app.services.admin_service import AdminError, AdminService
from app.services.wallet_service import WalletService
from burmaldoza_domain.economy import LedgerReason
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def replay_sessions():
    engine = create_async_engine(os.getenv("TEST_DATABASE_URL") or "sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        for table in reversed(Base.metadata.sorted_tables):
            await connection.execute(table.delete())
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        session.add_all([
            User(id=1, telegram_user_id=1001, display_name="Admin"),
            User(id=2, telegram_user_id=2002, display_name="Player"),
        ])
    yield factory
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["bonus", "reference", "other_wallet", "settlement", "delta"])
async def test_incompatible_key_returns_conflict_without_mutation(replay_sessions, scenario):
    key = uuid4()
    async with replay_sessions() as session:
        wallet = WalletService(session)
        if scenario == "settlement":
            await wallet.settle_game_round(2, uuid4(), 0, 250, key)
        else:
            async with session.begin():
                await wallet.apply_delta_in_transaction(
                    1 if scenario == "other_wallet" else 2,
                    251 if scenario == "delta" else 250,
                    LedgerReason.DAILY_BONUS if scenario == "bonus" else LedgerReason.ADMIN_ADJUSTMENT,
                    uuid4() if scenario == "reference" else None, key,
                )
    async with replay_sessions() as session:
        with pytest.raises(AdminError) as conflict:
            await AdminService(session, frozenset({1001})).adjust(1001, 2002, 250, "", key)
        assert conflict.value.status == 409
    async with replay_sessions() as session:
        assert await session.scalar(select(func.count()).select_from(LedgerEntry)) == 1
        assert await session.scalar(select(func.count()).select_from(AdminAuditLog)) == 0
        player = await session.get(Wallet, 2)
        assert (player.balance if player else 0) == (
            0 if scenario == "other_wallet" else 251 if scenario == "delta" else 250
        )


@pytest.mark.asyncio
async def test_matching_admin_key_replays_without_second_entry_or_audit(replay_sessions):
    key = uuid4()
    async with replay_sessions() as session:
        first = await AdminService(session, frozenset({1001})).adjust(1001, 2002, 250, "приз", key)
    async with replay_sessions() as session:
        replay = await AdminService(session, frozenset({1001})).adjust(1001, 2002, 250, "приз", key)
    assert first.replayed is False and replay.replayed is True
    assert first.operation_id == replay.operation_id
    assert (replay.balance_before, replay.balance_after) == (0, 250)
    async with replay_sessions() as session:
        assert (await session.get(Wallet, 2)).balance == 250
        assert await session.scalar(select(func.count()).select_from(LedgerEntry)) == 1
        assert await session.scalar(select(func.count()).select_from(AdminAuditLog)) == 1
