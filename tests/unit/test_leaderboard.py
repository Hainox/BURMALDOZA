from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from app.core.config import Settings
from app.db.models import Base, LedgerEntry, User, Wallet, WalletOperation
from app.db.session import get_session
from app.routers.leaderboard import get_leaderboard_now, router
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tests.unit.test_telegram_auth import BOT_TOKEN, make_init_data

NOW = datetime(2026, 10, 13, 10, tzinfo=UTC)
START = datetime(2026, 10, 11, 21, tzinfo=UTC)
END = START + timedelta(days=7)


@pytest_asyncio.fixture
async def leaderboard_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    app = FastAPI()
    app.state.settings = Settings(bot_token=BOT_TOKEN)
    app.include_router(router)

    async def session_override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_leaderboard_now] = lambda: NOW
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client, factory, app
    finally:
        await engine.dispose()


def signed(username="visitor"):
    user = {"id": 999, "first_name": "Private name"}
    if username is not None:
        user["username"] = username
    return {"X-Telegram-Init-Data": make_init_data(auth_date=datetime.now(UTC), user=user)}


async def add_player(factory, index, username, entries):
    async with factory() as session, session.begin():
        user = User(telegram_user_id=index, display_name="Do not expose", username=username)
        session.add(user)
        await session.flush()
        session.add(Wallet(user_id=user.id, balance=1000, version=0))
        await session.flush()
        for reason, delta, timestamp in entries:
            operation = WalletOperation(
                wallet_id=user.id,
                operation_type=reason,
                idempotency_key=uuid4(),
                reference_type="game_round",
            )
            session.add(operation)
            await session.flush()
            session.add(
                LedgerEntry(
                    operation_id=operation.id,
                    wallet_id=user.id,
                    amount_delta=delta,
                    balance_after=1000,
                    reason=reason,
                    reference_type="game_round",
                    created_at=timestamp,
                )
            )


@pytest.mark.asyncio
async def test_week_net_result_boundaries_grants_privacy_and_ties(leaderboard_db):
    client, factory, _app = leaderboard_db
    await add_player(
        factory,
        1,
        "winner",
        [
            ("game_stake", -50, START),
            ("game_payout", 100, NOW),
            ("daily_bonus", 9000, NOW),
            ("admin_adjustment", 9000, NOW),
            ("welcome", 9000, NOW),
            ("relief", 9000, NOW),
            ("game_payout", 9000, START - timedelta(microseconds=1)),
            ("game_payout", 9000, END),
        ],
    )
    await add_player(factory, 2, None, [("game_stake", -50, NOW)])
    await add_player(factory, 3, "tied", [("game_payout", 50, NOW)])
    await add_player(factory, 4, "grant_only", [("welcome", 1000, NOW)])
    response = await client.get("/api/v1/leaderboard", headers=signed())
    assert response.status_code == 200
    assert response.json() == {
        "week_start": "2026-10-11T21:00:00Z",
        "week_end": "2026-10-18T21:00:00Z",
        "entries": [
            {"rank": 1, "nickname": "@winner", "net_result": 50},
            {"rank": 2, "nickname": "@tied", "net_result": 50},
            {"rank": 3, "nickname": "Игрок без ника", "net_result": -50},
        ],
        "me": None,
    }
    assert "Do not expose" not in response.text
    for forbidden in ("user_id", "telegram_user_id", "display_name", "wallet_id"):
        assert forbidden not in response.text
    assert (await client.get("/api/v1/leaderboard", headers=signed())).json() == response.json()


@pytest.mark.asyncio
async def test_top15_and_signed_username_refresh_removal(leaderboard_db):
    client, factory, _app = leaderboard_db
    for index in range(1, 18):
        await add_player(factory, index, f"player{index}", [("game_payout", index, NOW)])
    response = await client.get("/api/v1/leaderboard", headers=signed("new_nick"))
    entries = response.json()["entries"]
    assert len(entries) == 15
    assert [entry["net_result"] for entry in entries] == list(range(17, 2, -1))
    async with factory() as session:
        assert (
            await session.scalar(select(User.username).where(User.telegram_user_id == 999))
            == "new_nick"
        )
    await client.get("/api/v1/leaderboard", headers=signed(None))
    async with factory() as session:
        assert (
            await session.scalar(select(User.username).where(User.telegram_user_id == 999)) is None
        )


@pytest.mark.asyncio
async def test_auth_empty_and_week_rollover(leaderboard_db):
    client, factory, app = leaderboard_db
    assert (await client.get("/api/v1/leaderboard")).status_code == 401
    assert (
        await client.get("/api/v1/leaderboard", headers={"X-Telegram-Init-Data": "forged"})
    ).status_code == 401
    await add_player(
        factory, 1, "last_week", [("game_payout", 100, END - timedelta(microseconds=1))]
    )
    app.dependency_overrides[get_leaderboard_now] = lambda: END
    response = await client.get("/api/v1/leaderboard", headers=signed())
    assert response.json()["week_start"] == "2026-10-18T21:00:00Z"
    assert response.json()["entries"] == []


async def caller_id(client, factory, username="visitor"):
    await client.get("/api/v1/leaderboard", headers=signed(username))
    async with factory() as session:
        return await session.scalar(select(User.id).where(User.telegram_user_id == 999))


async def add_entries(factory, user_id, entries):
    async with factory() as session, session.begin():
        if await session.get(Wallet, user_id) is None:
            session.add(Wallet(user_id=user_id, balance=1000, version=0))
            await session.flush()
        for reason, delta in entries:
            operation = WalletOperation(
                wallet_id=user_id,
                operation_type=reason,
                idempotency_key=uuid4(),
                reference_type="game_round",
            )
            session.add(operation)
            await session.flush()
            session.add(
                LedgerEntry(
                    operation_id=operation.id,
                    wallet_id=user_id,
                    amount_delta=delta,
                    balance_after=1000,
                    reason=reason,
                    reference_type="game_round",
                    created_at=NOW,
                )
            )


@pytest.mark.asyncio
async def test_own_place_is_returned_only_outside_the_top(leaderboard_db):
    client, factory, _app = leaderboard_db
    for index in range(1, 18):
        await add_player(factory, index, f"player{index}", [("game_payout", 100 + index, NOW)])
    # Without games this week the caller has no place at all.
    me_id = await caller_id(client, factory)
    assert (await client.get("/api/v1/leaderboard", headers=signed())).json()["me"] is None

    # Outside the top: 17 players are ahead, so the caller is 18th.
    await add_entries(factory, me_id, [("game_stake", -25)])
    body = (await client.get("/api/v1/leaderboard", headers=signed())).json()
    assert len(body["entries"]) == 15
    assert body["me"] == {"rank": 18, "nickname": "@visitor", "net_result": -25}
    for forbidden in ("user_id", "telegram_user_id", "display_name", "wallet_id"):
        assert forbidden not in str(body)

    # Inside the top the own row is not duplicated.
    await add_entries(factory, me_id, [("game_payout", 1000)])
    body = (await client.get("/api/v1/leaderboard", headers=signed())).json()
    assert body["me"] is None
    assert body["entries"][0] == {"rank": 1, "nickname": "@visitor", "net_result": 975}
