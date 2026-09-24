from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

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
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

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
