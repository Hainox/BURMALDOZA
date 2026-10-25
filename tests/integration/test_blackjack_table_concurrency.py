"""Shared-table races use actual PostgreSQL locks, with the process gate removed."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.db.models import GameAction, GamePlayer, GameRound, LedgerEntry, User
from app.services.blackjack_table_service import BlackjackTableService
from app.services.room_service import RoomService, RoomServiceError
from app.services.wallet_service import WalletService
from burmaldoza_contracts.rooms import ActionRequest
from burmaldoza_domain.core import StateVersionConflictError
from burmaldoza_domain.rng import SeededRandomSource
from sqlalchemy import func, select


@pytest.mark.asyncio
async def test_shared_blackjack_concurrent_create_join_start_timeout_replay(
    session_factory, monkeypatch
):
    import app.services.blackjack_table_service as module

    class NoProcessGate:
        async def __aenter__(self):
            await asyncio.sleep(0)

        async def __aexit__(self, *_):
            return None

    monkeypatch.setattr(module, "_TABLE_LOCK", NoProcessGate())
    async with session_factory() as session, session.begin():
        session.add_all([User(id=n, telegram_user_id=n, display_name="Test") for n in range(1, 5)])
    for n in range(1, 5):
        async with session_factory() as session:
            await WalletService(session).claim_welcome_grant(n, uuid4())
    now = [datetime.now(UTC)]

    def service(session):
        return BlackjackTableService(
            RoomService(session=session, now=lambda: now[0], blackjack_rng=SeededRandomSource(9))
        )

    key = uuid4()

    async def create():
        async with session_factory() as session:
            return await service(session).create(1, key)

    first, replayed = await asyncio.gather(create(), create())
    assert first == replayed

    async def join(user):
        async with session_factory() as session:
            return await service(session).join(first.room_id, user, uuid4())

    results = await asyncio.gather(*(join(n) for n in (2, 3, 4)), return_exceptions=True)
    assert sum(isinstance(r, RoomServiceError) for r in results) == 1
    async with session_factory() as session:
        members = list(
            (
                await session.scalars(
                    select(GamePlayer)
                    .where(GamePlayer.room_id == first.room_id)
                    .order_by(GamePlayer.seat)
                )
            ).all()
        )
    assert len(members) == 3 and len({m.seat for m in members}) == 3

    async def read(user):
        async with session_factory() as session:
            return await RoomService(session=session, now=lambda: now[0]).snapshot(
                first.room_id, user
            )

    async def act(user, action, action_id=None, version=None, **payload):
        snapshot = await read(user)
        async with session_factory() as session:
            return await service(session).apply(
                first.room_id,
                user,
                ActionRequest(
                    action_id=action_id or uuid4(),
                    expected_state_version=version
                    if version is not None
                    else snapshot.state_version,
                    payload={"action": action, **payload},
                ),
            )

    for member in members:
        await act(member.user_id, "ready", bet=25)
    snapshot = await read(1)
    startkey = uuid4()
    accepted, retry = await asyncio.gather(
        act(1, "start", startkey, snapshot.state_version),
        act(1, "start", startkey, snapshot.state_version),
    )
    assert accepted == retry
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(GameRound)) == 1
        assert (
            await session.scalar(
                select(func.count())
                .select_from(LedgerEntry)
                .where(LedgerEntry.reason == "game_stake")
            )
            == 3
        )
    current = await read(1)
    if current.public_state["phase"] == "active":
        now[0] += timedelta(seconds=20)

        async def expire():
            async with session_factory() as session:
                return await service(session).expire_due()

        counts = await asyncio.gather(expire(), expire())
        assert sum(counts) == 1
        actor = next(m.user_id for m in members if m.seat == current.public_state["active_seat"])
        with pytest.raises((RoomServiceError, StateVersionConflictError)):
            await act(actor, "hit", version=current.state_version)
    for _ in range(4):
        snapshot = await read(1)
        if snapshot.public_state["phase"] == "settled":
            break
        actor = next(m.user_id for m in members if m.seat == snapshot.public_state["active_seat"])
        await act(actor, "stand")
    assert (await read(1)).public_state["phase"] == "settled"
    async with session_factory() as session:
        assert (
            await session.scalar(
                select(func.count()).select_from(GameAction).where(GameAction.id == startkey)
            )
            == 1
        )
        assert (
            await session.scalar(
                select(func.count())
                .select_from(LedgerEntry)
                .where(LedgerEntry.reason == "game_stake")
            )
            == 3
        )
