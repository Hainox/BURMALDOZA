from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
from app.core.config import Settings
from app.db.models import Base, User
from app.db.session import get_session
from app.dependencies import CurrentUser, get_current_user, get_room_service
from app.main import app
from app.services.room_service import MemoryRoomStore, RoomService
from app.services.wallet_service import MemoryWalletStore, WalletService
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.unit.test_telegram_auth import BOT_TOKEN, make_init_data


def test_room_http_contract_replays_action_and_returns_snapshot_on_stale_request() -> None:
    wallet = WalletService(store=MemoryWalletStore())
    import asyncio

    asyncio.run(wallet.claim_welcome_grant(12345, uuid4()))
    service = RoomService(store=MemoryRoomStore(), wallet_service=wallet)
    user = CurrentUser(
        user_id=12345,
        telegram_user_id=12345,
        display_name="Ada Lovelace",
        username="ada",
    )
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_room_service] = lambda: service
    try:
        with TestClient(app) as client:
            created = client.post("/api/v1/rooms", json={"game_type": "slot", "mode": "solo"})
            assert created.status_code == 200
            room = created.json()
            action_id = str(uuid4())
            body = {
                "action_id": action_id,
                "expected_state_version": room["state_version"],
                "payload": {"action": "spin", "bet": 10},
            }

            first = client.post(
                f"/api/v1/rooms/{room['room_id']}/actions",
                json=body,
                headers={"X-Request-ID": action_id},
            )
            replay = client.post(
                f"/api/v1/rooms/{room['room_id']}/actions",
                json=body,
                headers={"X-Request-ID": action_id},
            )
            stale_action_id = str(uuid4())
            stale = client.post(
                f"/api/v1/rooms/{room['room_id']}/actions",
                json={**body, "action_id": stale_action_id},
                headers={"X-Request-ID": stale_action_id},
            )

            assert first.status_code == 200
            assert replay.status_code == 200
            assert replay.json() == first.json()
            result = first.json()["event"]["payload"]["result"]
            assert len(result["grid"]) == 3
            assert len(result["reel_stops"]) == 3
            assert result["balance_after"] == 1000 - 10 + result["gross_payout"]
            assert result == first.json()["event"]["payload"]["public_state"]["last_result"]
            assert stale.status_code == 409
            assert stale.json()["detail"]["snapshot"]["state_version"] == 1
    finally:
        app.dependency_overrides.clear()


def test_protected_http_route_rejects_missing_telegram_auth() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/games")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_telegram_auth_route_verifies_and_persists_minimal_user() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_session():
        async with session_factory() as session:
            yield session

    previous_settings = app.state.settings
    app.state.settings = Settings(bot_token=BOT_TOKEN)
    app.dependency_overrides[get_session] = override_session
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/telegram",
                json={"init_data": make_init_data(auth_date=datetime.now(UTC) - timedelta(minutes=5))},
            )

        assert response.status_code == 200
        assert response.json()["telegram_user_id"] == 12345
        async with session_factory() as session:
            user = (await session.execute(select(User).where(User.telegram_user_id == 12345))).scalar_one()
            assert user is not None
    finally:
        app.dependency_overrides.clear()
        app.state.settings = previous_settings
        await engine.dispose()


def test_room_websocket_closes_when_client_never_authenticates(monkeypatch) -> None:
    from app.routers import rooms
    from starlette.websockets import WebSocketDisconnect

    monkeypatch.setattr(rooms, "WEBSOCKET_AUTH_TIMEOUT_SECONDS", 0.05)
    with (
        TestClient(app) as client,
        client.websocket_connect(f"/api/v1/rooms/{uuid4()}/events") as websocket,
        pytest.raises(WebSocketDisconnect) as closed,
    ):
        websocket.receive_json()

    assert closed.value.code == 4401
    assert closed.value.reason == "authentication timeout"


@pytest.mark.asyncio
async def test_first_login_grants_welcome_once_and_faucets_are_claimable() -> None:
    from app.db.models import LedgerEntry

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_session():
        async with session_factory() as session:
            yield session

    previous_settings = app.state.settings
    app.state.settings = Settings(bot_token=BOT_TOKEN)
    app.dependency_overrides[get_session] = override_session
    headers = {"X-Telegram-Init-Data": make_init_data(auth_date=datetime.now(UTC) - timedelta(minutes=5))}
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.get("/api/v1/wallet", headers=headers)
            again = await client.get("/api/v1/wallet", headers=headers)
            relief = await client.post(
                "/api/v1/wallet/relief/claim", headers={**headers, "X-Request-ID": str(uuid4())}
            )
            daily = await client.post(
                "/api/v1/wallet/daily-bonus/claim", headers={**headers, "X-Request-ID": str(uuid4())}
            )
            daily_again = await client.post(
                "/api/v1/wallet/daily-bonus/claim", headers={**headers, "X-Request-ID": str(uuid4())}
            )

        assert first.status_code == 200
        assert first.json()["balance"] == 1000
        assert again.json()["balance"] == 1000
        assert relief.status_code == 409  # balance is above the relief threshold
        assert daily.status_code == 200
        assert daily.json()["balance_after"] == 1250
        assert daily_again.status_code == 409  # 24h cooldown
        async with session_factory() as session:
            reasons = sorted((await session.execute(select(LedgerEntry.reason))).scalars())
        assert reasons == ["daily_bonus", "welcome"]
    finally:
        app.dependency_overrides.clear()
        app.state.settings = previous_settings
        await engine.dispose()


@asynccontextmanager
async def _sqlite_api() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_session():
        async with session_factory() as session:
            yield session

    previous_settings = app.state.settings
    app.state.settings = Settings(bot_token=BOT_TOKEN)
    app.dependency_overrides[get_session] = override_session
    try:
        yield session_factory
    finally:
        app.dependency_overrides.clear()
        app.state.settings = previous_settings
        await engine.dispose()


def _auth_headers(telegram_user_id: int) -> dict[str, str]:
    user = {"id": telegram_user_id, "first_name": f"Player {telegram_user_id}"}
    return {
        "X-Telegram-Init-Data": make_init_data(
            auth_date=datetime.now(UTC) - timedelta(minutes=5), user=user
        )
    }


@pytest.mark.asyncio
async def test_operation_at_old_predictable_welcome_key_does_not_block_next_first_login() -> None:
    async with _sqlite_api() as session_factory:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.get("/api/v1/wallet", headers=_auth_headers(111))
            first_user_id = first.json()["user_id"]
            # The former scheme keyed the welcome grant by the next sequential user id.
            predicted_key = uuid5(NAMESPACE_URL, f"burmaldoza:welcome-grant:{first_user_id + 1}")
            async with session_factory() as session:
                await WalletService(session).settle_game_round(
                    first_user_id, uuid4(), stake=10, payout=0, idempotency_key=predicted_key
                )

            second = await client.get("/api/v1/wallet", headers=_auth_headers(222))

        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["user_id"] == first_user_id + 1
        assert second.json()["balance"] == 1000


@pytest.mark.asyncio
async def test_reusing_daily_request_id_for_relief_is_a_conflict() -> None:
    async with _sqlite_api():
        transport = ASGITransport(app=app)
        headers = {**_auth_headers(333), "X-Request-ID": str(uuid4())}
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            daily = await client.post("/api/v1/wallet/daily-bonus/claim", headers=headers)
            relief = await client.post("/api/v1/wallet/relief/claim", headers=headers)
            daily_replay = await client.post("/api/v1/wallet/daily-bonus/claim", headers=headers)
            balance = await client.get("/api/v1/wallet", headers=headers)

        assert daily.status_code == 200
        assert relief.status_code == 409
        assert relief.json()["detail"] == "idempotency key belongs to another wallet operation"
        assert daily_replay.status_code == 200
        assert daily_replay.json() == daily.json()
        assert balance.json()["balance"] == 1250


@pytest.mark.asyncio
async def test_wallet_request_id_from_another_user_is_a_conflict_in_database() -> None:
    async with _sqlite_api():
        transport = ASGITransport(app=app)
        request_id = str(uuid4())
        first_headers = {**_auth_headers(444), "X-Request-ID": request_id}
        second_headers = {**_auth_headers(555), "X-Request-ID": request_id}
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.post("/api/v1/wallet/daily-bonus/claim", headers=first_headers)
            second = await client.post("/api/v1/wallet/daily-bonus/claim", headers=second_headers)
            first_wallet = await client.get("/api/v1/wallet", headers=first_headers)
            second_wallet = await client.get("/api/v1/wallet", headers=second_headers)

        assert first.status_code == 200
        assert second.status_code == 409
        assert second.json()["detail"] == "idempotency key belongs to another wallet"
        assert first_wallet.json()["balance"] == 1250
        assert second_wallet.json()["balance"] == 1000


@pytest.mark.asyncio
async def test_ledger_orders_settlement_payout_before_stake_with_equal_timestamps() -> None:
    from uuid import UUID

    from app.db.models import LedgerEntry

    async with _sqlite_api() as session_factory:
        transport = ASGITransport(app=app)
        headers = _auth_headers(67001)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            wallet = (await client.get("/api/v1/wallet", headers=headers)).json()
            other = (await client.get("/api/v1/wallet", headers=_auth_headers(67002))).json()
            async with session_factory() as session:
                settlement = await WalletService(session).settle_game_round(
                    wallet["user_id"], uuid4(), stake=10, payout=30, idempotency_key=uuid4()
                )
                entries = (await session.scalars(select(LedgerEntry).where(
                    LedgerEntry.operation_id == settlement.operation_id
                ))).all()
                timestamp = datetime.now(UTC) + timedelta(seconds=1)
                for entry in entries:
                    entry.created_at = timestamp
                    # UUID ordering intentionally puts the earlier debit first.
                    entry.id = UUID(int=2 if entry.reason == "game_stake" else 1)
                await session.commit()
            for _ in range(50):
                async with session_factory() as session:
                    await WalletService(session).settle_game_round(
                        wallet["user_id"], uuid4(), stake=1, payout=1, idempotency_key=uuid4()
                    )
            response = await client.get("/api/v1/wallet/ledger", headers=headers)
            outsider = await client.get("/api/v1/wallet/ledger", headers=_auth_headers(67002))
            unauthenticated = await client.get("/api/v1/wallet/ledger")

        assert response.status_code == 200
        assert [entry["reason"] for entry in response.json()[:2]] == ["game_payout", "game_stake"]
        assert [entry["balance_after"] for entry in response.json()[:2]] == [1020, 990]
        assert len(response.json()) == 100
        assert [entry["reason"] for entry in outsider.json()] == ["welcome"]
        assert other["balance"] == 1000
        assert unauthenticated.status_code == 401


def test_slot_catalog_exposes_siege_and_keeps_skeleton_metadata() -> None:
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(1, 1, "Player")
    try:
        with TestClient(app) as client:
            games = client.get("/api/v1/games").json()
            assert next(game for game in games if game["game_type"] == "slot")["ruleset_version"] == "slot-siege-2"
            for version in ("slot-skeleton-1", "slot-siege-1", "slot-siege-2"):
                response = client.get(f"/api/v1/rulesets/slot/{version}")
                assert response.status_code == 200
                assert response.json()["version"] == version
            assert client.get("/api/v1/rulesets/slot/unknown").status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_persisted_skeleton_room_uses_old_rules_after_api_upgrade() -> None:
    from burmaldoza_domain.games.slot_ruleset import load_skeleton_config

    async with _sqlite_api() as session_factory:
        transport = ASGITransport(app=app)
        headers = _auth_headers(64001)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            wallet = (await client.get("/api/v1/wallet", headers=headers)).json()
            async with session_factory() as session:
                old = await RoomService(session=session, slot_config=load_skeleton_config()).create_room(
                    wallet["user_id"], "slot", "solo"
                )
            new = (await client.post("/api/v1/rooms", headers=headers,
                json={"game_type": "slot", "mode": "solo"})).json()
            assert new["ruleset_version"] == "slot-siege-2"
            for room_id, version in ((str(old.room_id), "slot-skeleton-1"), (new["room_id"], "slot-siege-2")):
                action_id = str(uuid4())
                response = await client.post(f"/api/v1/rooms/{room_id}/actions", headers=headers,
                    json={"action_id": action_id, "expected_state_version": 0,
                          "payload": {"action": "spin", "bet": 10}})
                assert response.status_code == 200
                assert response.json()["event"]["ruleset_version"] == version
                assert response.json()["event"]["payload"]["result"]["ruleset_version"] == version
