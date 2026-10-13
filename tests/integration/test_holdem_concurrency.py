"""Actual PostgreSQL row/advisory lock regression gates (run in CI)."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.db.models import GameAction, LedgerEntry, User
from app.services.holdem_service import HoldemService
from app.services.room_service import RoomService, RoomServiceError
from app.services.wallet_service import WalletService
from burmaldoza_contracts.common import GameType
from burmaldoza_contracts.rooms import ActionRequest
from sqlalchemy import func, select


async def users(factory):
    async with factory() as session, session.begin():
        session.add_all([User(id=n, telegram_user_id=n, display_name="Test") for n in (1, 2, 3)])
    for n in (1, 2, 3):
        async with factory() as session:
            await WalletService(session).claim_welcome_grant(n, uuid4())


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["bot", "pvp"])
async def test_concurrent_holdem_create_action_and_timeout_are_exactly_once(
    session_factory, mode, monkeypatch
):
    import app.services.holdem_service as module

    class IndependentProcesses:
        # Remove the per-process gate to exercise actual PostgreSQL locking.
        async def __aenter__(self):
            await asyncio.sleep(0)

        async def __aexit__(self, *_):
            return None

    monkeypatch.setattr(module, "_QUEUE_LOCK", IndependentProcesses())
    await users(session_factory)
    key = uuid4()
    now = datetime.now(UTC)

    async def create(user, action_id, mode=mode):
        async with session_factory() as session:
            return await RoomService(session=session, now=lambda: now).create_room(
                user, GameType.HOLDEM, mode, buy_in=100, action_id=action_id
            )

    first, replay = await asyncio.gather(create(1, key), create(1, key))
    assert first == replay
    if mode == "pvp":
        secondkey = uuid4()
        second, secondreplay = await asyncio.gather(create(2, secondkey), create(2, secondkey))
        assert second == secondreplay and second.room_id == first.room_id
        async with session_factory() as session:
            first = await RoomService(session=session).snapshot(first.room_id, 1)
    request = ActionRequest(
        action_id=uuid4(), expected_state_version=first.state_version, payload={"action": "fold"}
    )

    async def fold():
        async with session_factory() as session:
            return await RoomService(session=session).apply_action(first.room_id, 1, request)

    event, replayed = await asyncio.gather(fold(), fold())
    assert event == replayed
    async with session_factory() as session:
        stakes = await session.scalar(
            select(func.count()).select_from(LedgerEntry).where(LedgerEntry.reason == "game_stake")
        )
        assert stakes == (2 if mode == "pvp" else 1)
        assert (
            await session.scalar(
                select(func.count())
                .select_from(GameAction)
                .where(GameAction.id == request.action_id)
            )
            == 1
        )
    if mode == "pvp":
        waitkey = uuid4()
        results = await asyncio.gather(
            create(3, waitkey), create(3, uuid4()), return_exceptions=True
        )
        assert sum(isinstance(result, RoomServiceError) for result in results) == 1

        async def expire():
            async with session_factory() as session:
                return await HoldemService(
                    RoomService(session=session, now=lambda: now + timedelta(seconds=60))
                ).expire_due()

        counts = await asyncio.gather(expire(), expire())
        assert sum(counts) == 1
        async with session_factory() as session:
            assert (await WalletService(session).get_or_create(3)).balance == 1000
