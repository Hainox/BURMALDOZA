from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from app.db.models import Base, GameAction, GameRoom, LedgerEntry, User
from app.services.holdem_table_service import HoldemTableService
from app.services.room_service import RoomAccessError, RoomService
from app.services.wallet_service import WalletService
from burmaldoza_contracts.rooms import ActionRequest
from burmaldoza_domain.rng import SeededRandomSource
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def table_db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/six.db")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with factory() as session, session.begin():
        session.add_all(User(id=i, telegram_user_id=i, display_name="Test") for i in range(1, 9))
    for i in range(1, 9):
        async with factory() as session:
            await WalletService(session).claim_welcome_grant(i, uuid4())
    clock = [datetime(2026, 10, 22, tzinfo=UTC)]

    def service(session):
        return HoldemTableService(
            RoomService(session=session, now=lambda: clock[0], holdem_rng=SeededRandomSource(9))
        )

    yield factory, service, clock
    await engine.dispose()


async def create(db, user, action_id=None):
    factory, service, _ = db
    async with factory() as s:
        return await service(s).create(user, 100, action_id or uuid4())


@pytest.mark.asyncio
async def test_six_join_same_room_and_full_cycle_conserves_entries(table_db):
    factory, service, _ = table_db
    snapshots = [await create(table_db, i) for i in range(1, 7)]
    assert len({v.room_id for v in snapshots}) == 1
    snap = snapshots[-1]
    assert snap.public_state["phase"] == "active"
    for _ in range(60):
        async with factory() as s, s.begin():
            room = await s.get(GameRoom, snap.room_id)
            state = room.state_json
            if state["phase"] == "settled":
                break
            seat = state["current_seat"]
            members = await service(s).members(room.id)
            view = await service(s).project_snapshot(room, members[seat])
        async with factory() as s:
            event = await service(s).apply(
                snap.room_id,
                members[seat],
                ActionRequest(
                    action_id=uuid4(),
                    expected_state_version=view.state_version,
                    payload={
                        "action": "check"
                        if "check" in view.public_state["legal_actions"]
                        else "call"
                    },
                ),
            )
        assert event.payload["public_state"]["viewer_seat"] == seat
    else:
        pytest.fail("hand did not terminate")
    assert sum(state["last_result"]["cashouts"].values()) == 600
    async with factory() as s:
        actions = list((await s.scalars(select(GameAction))).all())
        assert all(
            "hole_cards" not in str(a.payload_json) and "wallet_balance" not in str(a.payload_json)
            for a in actions
        )


@pytest.mark.asyncio
async def test_deadline_starts_two_and_cancel_is_personal_and_replayable(table_db):
    factory, service, clock = table_db
    first_id = uuid4()
    first = await create(table_db, 1, first_id)
    second = await create(table_db, 2)
    async with factory() as s:
        event = await service(s).apply(
            first.room_id,
            1,
            ActionRequest(
                action_id=uuid4(),
                expected_state_version=second.state_version,
                payload={"action": "cancel"},
            ),
        )
    assert event.payload["public_state"]["phase"] == "cancelled"
    replay = await create(table_db, 1, first_id)
    assert replay.public_state["phase"] == "cancelled"
    await create(table_db, 3)
    clock[0] += timedelta(seconds=61)
    async with factory() as s:
        assert await service(s).expire_due() == 1
    async with factory() as s, s.begin():
        room = await s.get(GameRoom, first.room_id)
        assert room.status == "active"
        with pytest.raises(RoomAccessError):
            await service(s).project_snapshot(room, 1)


@pytest.mark.asyncio
async def test_lone_search_expires_without_stake(table_db):
    factory, service, clock = table_db
    snap = await create(table_db, 1)
    clock[0] += timedelta(seconds=61)
    async with factory() as s:
        await service(s).expire_due()
    async with factory() as s:
        room = await s.get(GameRoom, snap.room_id)
        assert room.status == "closed"
        assert (
            await s.scalar(
                select(func.count())
                .select_from(LedgerEntry)
                .where(LedgerEntry.reason == "game_stake")
            )
            == 0
        )


@pytest.mark.asyncio
async def test_cancel_then_rejoin_creation_replays_independently(table_db):
    factory, service, _ = table_db
    original_id = uuid4()
    first = await create(table_db, 1, original_id)
    other = await create(table_db, 2)
    cancel_id = uuid4()
    async with factory() as s:
        await service(s).apply(
            first.room_id,
            1,
            ActionRequest(
                action_id=cancel_id,
                expected_state_version=other.state_version,
                payload={"action": "cancel"},
            ),
        )
    new_id = uuid4()
    rejoined = await create(table_db, 1, new_id)
    assert rejoined.room_id == first.room_id
    assert (await create(table_db, 1, original_id)).public_state["phase"] == "cancelled"
    assert (await create(table_db, 1, new_id)).public_state["phase"] == "waiting"


@pytest.mark.asyncio
async def test_delayed_waiting_event_never_gains_cards(table_db):
    factory, service, _ = table_db
    first = await create(table_db, 1)
    for user in range(2, 7):
        await create(table_db, user)
    async with factory() as s, s.begin():
        room = await s.get(GameRoom, first.room_id)
        old = await s.scalar(
            select(GameAction)
            .where(GameAction.room_id == first.room_id)
            .order_by(GameAction.sequence_no)
        )
        projected = await service(s).project_event(
            room, service(s).rooms._event_from_action(room, old), 1
        )
        assert projected.payload["public_state"]["hole_cards"] == []
        assert all(p["cards"] == [] for p in projected.payload["public_state"]["players"])


@pytest.mark.asyncio
async def test_old_roster_event_survives_departure(table_db):
    factory, service, _ = table_db
    first = await create(table_db, 1)
    second = await create(table_db, 2)
    async with factory() as s:
        await service(s).apply(
            first.room_id,
            2,
            ActionRequest(
                action_id=uuid4(),
                expected_state_version=second.state_version,
                payload={"action": "cancel"},
            ),
        )
    async with factory() as s, s.begin():
        room = await s.get(GameRoom, first.room_id)
        old = await s.scalar(
            select(GameAction).where(
                GameAction.room_id == first.room_id, GameAction.sequence_no == second.state_version
            )
        )
        view = await service(s).project_event(
            room, service(s).rooms._event_from_action(room, old), 1
        )
        assert view.payload["public_state"]["players"][1]["avatar_path"] is None


@pytest.mark.asyncio
async def test_insolvent_seat_removed_but_partial_roster_waits_original_deadline(table_db):
    from burmaldoza_domain.economy import LedgerReason

    factory, _, _ = table_db
    first = await create(table_db, 1)
    for user in range(2, 6):
        await create(table_db, user)
    async with factory() as s:
        await WalletService(s).apply_delta(1, -1000, LedgerReason.GAME_STAKE, uuid4(), uuid4())
    sixth = await create(table_db, 6)
    assert sixth.public_state["phase"] == "waiting"
    assert len(sixth.public_state["players"]) == 5
    assert sixth.public_state["search_deadline"] == first.public_state["search_deadline"]


@pytest.mark.asyncio
async def test_expired_multiway_queue_cannot_duplicate_before_tick(table_db):
    from app.services.room_service import RoomServiceError

    _, _, clock = table_db
    await create(table_db, 1)
    await create(table_db, 2)
    clock[0] += timedelta(seconds=61)
    with pytest.raises(RoomServiceError):
        await create(table_db, 1)


@pytest.mark.asyncio
async def test_expired_six_queue_prevents_legacy_create(table_db):
    from app.services.room_service import RoomServiceError
    from burmaldoza_contracts.common import GameType

    factory, service, clock = table_db
    await create(table_db, 1)
    await create(table_db, 2)
    clock[0] += timedelta(seconds=61)
    async with factory() as s:
        with pytest.raises(RoomServiceError):
            await service(s).rooms.create_room(
                1, GameType.HOLDEM, "pvp", buy_in=100, action_id=uuid4()
            )


@pytest.mark.asyncio
async def test_cancelled_creation_receipt_is_stable_after_roster_changes(table_db):
    factory, service, _ = table_db
    original = uuid4()
    snap = await create(table_db, 1, original)
    other = await create(table_db, 2)
    async with factory() as s:
        await service(s).apply(
            snap.room_id,
            1,
            ActionRequest(
                action_id=uuid4(),
                expected_state_version=other.state_version,
                payload={"action": "cancel"},
            ),
        )
    first_receipt = await create(table_db, 1, original)
    await create(table_db, 3)
    later_receipt = await create(table_db, 1, original)
    assert first_receipt == later_receipt


@pytest.mark.asyncio
async def test_settlement_never_reveals_folded_or_old_active_event_cards(table_db):
    factory, service, clock = table_db
    first = await create(table_db, 1)
    await create(table_db, 2)
    await create(table_db, 3)
    clock[0] += timedelta(seconds=60)
    async with factory() as s:
        await service(s).expire_due()
    folded_seat = None
    old_action = None
    while True:
        async with factory() as s, s.begin():
            room = await s.get(GameRoom, first.room_id)
            if room.status == "settled":
                break
            members = await service(s).members(room.id)
            seat = room.state_json["current_seat"]
            snapshot = await service(s).project_snapshot(room, members[seat])
        action = (
            "fold"
            if folded_seat is None
            else "check"
            if "check" in snapshot.public_state["legal_actions"]
            else "call"
        )
        async with factory() as s:
            event = await service(s).apply(
                first.room_id,
                members[seat],
                ActionRequest(
                    action_id=uuid4(),
                    expected_state_version=snapshot.state_version,
                    payload={"action": action},
                ),
            )
        if folded_seat is None:
            folded_seat = seat
            old_action = event.event_id
    async with factory() as s, s.begin():
        room = await s.get(GameRoom, first.room_id)
        members = await service(s).members(room.id)
        viewer = next(seat for seat in members if seat != folded_seat)
        settled = await service(s).project_snapshot(room, members[viewer])
        folded = next(p for p in settled.public_state["players"] if p["seat"] == folded_seat)
        assert folded["cards"] == [{"hidden": True}, {"hidden": True}]
        old = await s.get(GameAction, old_action)
        projected = await service(s).project_event(
            room, service(s).rooms._event_from_action(room, old), members[viewer]
        )
        for player in projected.payload["public_state"]["players"]:
            if player["seat"] != viewer:
                assert player["cards"] == [{"hidden": True}, {"hidden": True}]


@pytest.mark.asyncio
async def test_raise_bound_null_when_viewer_cannot_raise_and_cancel_ws_receipt(table_db):
    factory, service, _ = table_db
    first = await create(table_db, 1)
    second = await create(table_db, 2)
    async with factory() as s:
        cancelled = await service(s).apply(
            first.room_id,
            1,
            ActionRequest(
                action_id=uuid4(),
                expected_state_version=second.state_version,
                payload={"action": "cancel"},
            ),
        )
    async with factory() as s, s.begin():
        room = await s.get(GameRoom, first.room_id)
        action = await s.get(GameAction, cancelled.event_id)
        bus = service(s).rooms._event_from_action(room, action)
        own = await service(s).project_event(room, bus, 1)
        assert own == cancelled
        other = await service(s).project_event(room, bus, 2)
        assert other.payload["public_state"]["phase"] == "waiting"
        assert other.payload["public_state"]["min_raise_to"] is None
        with pytest.raises(RoomAccessError):
            await service(s).project_event(room, bus, 3)
    third = await create(table_db, 3)
    async with factory() as s, s.begin():
        room = await s.get(GameRoom, first.room_id)
        action = await s.scalar(
            select(GameAction).where(
                GameAction.room_id == first.room_id, GameAction.sequence_no == third.state_version
            )
        )
        with pytest.raises(RoomAccessError):
            await service(s).project_event(
                room, service(s).rooms._event_from_action(room, action), 1
            )
