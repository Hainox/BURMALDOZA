"""Exercise durable queue/room locks without the single-process serialization gate."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.db.models import GameAction, GamePlayer, GameRoom, GameRound, LedgerEntry, User
from app.services.holdem_table_service import HoldemTableService
from app.services.room_service import RoomService
from app.services.wallet_service import WalletService
from burmaldoza_contracts.rooms import ActionRequest
from sqlalchemy import func, select


class IndependentProcesses:
    async def __aenter__(self):
        await asyncio.sleep(0)

    async def __aexit__(self, *_):
        return None


async def prepare(factory):
    async with factory() as s, s.begin():
        s.add_all(User(id=n, telegram_user_id=n, display_name="Test") for n in range(1, 8))
    for n in range(1, 8):
        async with factory() as s:
            await WalletService(s).claim_welcome_grant(n, uuid4())


@pytest.mark.asyncio
async def test_postgres_six_simultaneous_joins_and_seventh_new_room(session_factory, monkeypatch):
    import app.services.holdem_table_service as module

    monkeypatch.setattr(module, "_QUEUE_LOCK", IndependentProcesses())
    await prepare(session_factory)
    now = datetime.now(UTC)

    async def create(user, key=None):
        async with session_factory() as s:
            return await HoldemTableService(RoomService(session=s, now=lambda: now)).create(
                user, 100, key or uuid4()
            )

    snapshots = await asyncio.gather(*(create(user) for user in range(1, 8)))
    active = [s for s in snapshots if s.public_state["phase"] == "active"]
    assert len(active) == 1
    room_id = active[0].room_id
    async with session_factory() as s:
        assert (
            await s.scalar(
                select(func.count()).select_from(GamePlayer).where(GamePlayer.room_id == room_id)
            )
            == 6
        )
        assert await s.scalar(select(func.count()).select_from(GameRound)) == 1
        assert (
            await s.scalar(
                select(func.count())
                .select_from(LedgerEntry)
                .where(LedgerEntry.reason == "game_stake")
            )
            == 6
        )
        assert (
            await s.scalar(
                select(func.count()).select_from(GameRoom).where(GameRoom.status == "waiting")
            )
            == 1
        )


@pytest.mark.asyncio
async def test_postgres_deadline_race_and_settlement_replay_once(session_factory, monkeypatch):
    import app.services.holdem_table_service as module

    monkeypatch.setattr(module, "_QUEUE_LOCK", IndependentProcesses())
    await prepare(session_factory)
    clock = [datetime.now(UTC)]

    def service(s):
        return HoldemTableService(RoomService(session=s, now=lambda: clock[0]))

    key = uuid4()

    async def create(user, key):
        async with session_factory() as s:
            return await service(s).create(user, 100, key)

    first, replay = await asyncio.gather(create(1, key), create(1, key))
    assert first == replay
    second = await create(2, uuid4())
    clock[0] += timedelta(seconds=60)

    async def expire():
        async with session_factory() as s:
            return await service(s).expire_due()

    assert sum(await asyncio.gather(expire(), expire())) == 1
    async with session_factory() as s, s.begin():
        room = await s.get(GameRoom, first.room_id)
        seat = room.state_json["current_seat"]
        user = (await service(s).members(room.id))[seat]
        version = room.state_version
    request = ActionRequest(
        action_id=uuid4(), expected_state_version=version, payload={"action": "fold"}
    )

    async def fold():
        async with session_factory() as s:
            return await service(s).apply(second.room_id, user, request)

    event, replayed = await asyncio.gather(fold(), fold())
    assert event == replayed
    async with session_factory() as s:
        assert (
            await s.scalar(
                select(func.count())
                .select_from(GameAction)
                .where(GameAction.id == request.action_id)
            )
            == 1
        )
        assert (
            await s.scalar(
                select(func.count())
                .select_from(LedgerEntry)
                .where(LedgerEntry.reason == "game_stake")
            )
            == 2
        )
        payouts = list(
            (
                await s.scalars(
                    select(LedgerEntry.amount_delta).where(LedgerEntry.reason == "game_payout")
                )
            ).all()
        )
        assert sum(payouts) == 200


@pytest.mark.asyncio
async def test_postgres_cancel_vs_sixth_join_has_no_partial_stakes(session_factory, monkeypatch):
    import app.services.holdem_table_service as module

    monkeypatch.setattr(module, "_QUEUE_LOCK", IndependentProcesses())
    await prepare(session_factory)
    now = datetime.now(UTC)

    def service(s):
        return HoldemTableService(RoomService(session=s, now=lambda: now))

    async def create(user):
        async with session_factory() as s:
            return await service(s).create(user, 100, uuid4())

    snapshots = [await create(n) for n in range(1, 6)]
    room_id = snapshots[0].room_id
    request = ActionRequest(
        action_id=uuid4(),
        expected_state_version=snapshots[-1].state_version,
        payload={"action": "cancel"},
    )

    async def cancel():
        async with session_factory() as s:
            return await service(s).apply(room_id, 1, request)

    await asyncio.gather(cancel(), create(6), return_exceptions=True)
    async with session_factory() as s:
        room = await s.get(GameRoom, room_id)
        count = await s.scalar(
            select(func.count()).select_from(LedgerEntry).where(LedgerEntry.reason == "game_stake")
        )
        assert (room.status, count) in [("waiting", 0), ("active", 6)]


@pytest.mark.asyncio
async def test_postgres_last_stake_collision_rolls_back_whole_start(session_factory, monkeypatch):
    from uuid import uuid5

    import app.services.holdem_table_service as module
    from app.services.room_service import RoomServiceError
    from burmaldoza_domain.economy import LedgerReason

    monkeypatch.setattr(module, "_QUEUE_LOCK", IndependentProcesses())
    await prepare(session_factory)

    async def create(user):
        async with session_factory() as s:
            return await HoldemTableService(RoomService(session=s)).create(user, 100, uuid4())

    snaps = [await create(n) for n in range(1, 6)]
    room_id = snaps[0].room_id
    async with session_factory() as s:
        await WalletService(s).apply_delta(
            7, 1, LedgerReason.DAILY_BONUS, room_id, uuid5(room_id, "stake:6")
        )
    with pytest.raises(RoomServiceError):
        await create(6)
    async with session_factory() as s:
        assert (
            await s.scalar(
                select(func.count())
                .select_from(LedgerEntry)
                .where(LedgerEntry.reason == "game_stake")
            )
            == 0
        )
        assert await s.scalar(select(func.count()).select_from(GameRound)) == 0
        assert (
            await s.scalar(
                select(func.count()).select_from(GamePlayer).where(GamePlayer.room_id == room_id)
            )
            == 5
        )
        assert (await s.get(GameRoom, room_id)).status == "waiting"


@pytest.mark.asyncio
async def test_postgres_exact_deadline_action_loses_to_timeout(session_factory, monkeypatch):
    import app.services.holdem_table_service as module
    from app.services.room_service import RoomServiceError

    monkeypatch.setattr(module, "_QUEUE_LOCK", IndependentProcesses())
    await prepare(session_factory)
    clock = [datetime.now(UTC)]

    def service(s):
        return HoldemTableService(RoomService(session=s, now=lambda: clock[0]))

    async def create(user):
        async with session_factory() as s:
            return await service(s).create(user, 100, uuid4())

    snaps = [await create(n) for n in range(1, 7)]
    room_id = snaps[0].room_id
    async with session_factory() as s, s.begin():
        room = await s.get(GameRoom, room_id)
        user = (await service(s).members(room_id))[room.state_json["current_seat"]]
        request = ActionRequest(
            action_id=uuid4(), expected_state_version=room.state_version, payload={"action": "call"}
        )
        clock[0] = room.deadline_at

    async def move():
        async with session_factory() as s:
            return await service(s).apply(room_id, user, request)

    async def tick():
        async with session_factory() as s:
            return await service(s).expire_due()

    moved, ticked = await asyncio.gather(move(), tick(), return_exceptions=True)
    assert isinstance(moved, (RoomServiceError, ValueError))
    assert ticked == 1
    async with session_factory() as s:
        assert (
            await s.scalar(
                select(func.count())
                .select_from(GameAction)
                .where(GameAction.id == request.action_id)
            )
            == 0
        )


@pytest.mark.asyncio
async def test_postgres_last_payout_collision_rolls_back_whole_settlement(
    session_factory, monkeypatch
):
    from uuid import uuid5

    import app.services.holdem_table_service as module
    from app.services.room_service import RoomServiceError
    from burmaldoza_domain.economy import LedgerReason

    monkeypatch.setattr(module, "_QUEUE_LOCK", IndependentProcesses())
    await prepare(session_factory)

    def service(s):
        return HoldemTableService(RoomService(session=s))

    async def create(user):
        async with session_factory() as s:
            return await service(s).create(user, 100, uuid4())

    snaps = [await create(n) for n in range(1, 7)]
    room_id = snaps[0].room_id
    for _ in range(40):
        async with session_factory() as s, s.begin():
            room = await s.get(GameRoom, room_id)
            state = room.private_state_json["state"]
            seat = room.state_json["current_seat"]
            members = await service(s).members(room_id)
            view = await service(s).project_snapshot(room, members[seat])
            final = state["phase"] == "river" and len(state["pending_seats"]) == 1
        action = "check" if "check" in view.public_state["legal_actions"] else "call"
        request = ActionRequest(
            action_id=uuid4(), expected_state_version=view.state_version, payload={"action": action}
        )
        if final:
            async with session_factory() as s:
                await WalletService(s).apply_delta(
                    7, 1, LedgerReason.DAILY_BONUS, room_id, uuid5(room_id, "payout:6")
                )
            async with session_factory() as s:
                with pytest.raises(RoomServiceError):
                    await service(s).apply(room_id, members[seat], request)
            break
        async with session_factory() as s:
            await service(s).apply(room_id, members[seat], request)
    else:
        pytest.fail("final river action not reached")
    async with session_factory() as s:
        room = await s.get(GameRoom, room_id)
        assert room.status == "active" and room.state_version == view.state_version
        assert (
            await s.scalar(
                select(func.count())
                .select_from(LedgerEntry)
                .where(LedgerEntry.reason == "game_payout")
            )
            == 0
        )
        assert await s.get(GameAction, request.action_id) is None
