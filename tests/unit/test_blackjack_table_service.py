import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from app.db.models import Base, GameAction, GameRoom, GameRound, User
from app.services.blackjack_table_service import BlackjackTableService
from app.services.room_service import RoomAccessError, RoomService, RoomServiceError
from app.services.wallet_service import WalletService
from burmaldoza_contracts.rooms import ActionRequest
from burmaldoza_domain.core import StateVersionConflictError
from burmaldoza_domain.rng import SeededRandomSource
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def table_db(tmp_path, monkeypatch):
    import app.services.blackjack_table_service as module

    monkeypatch.setattr(module, "_TABLE_LOCK", asyncio.Lock())
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'table.db').as_posix()}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as session, session.begin():
        session.add_all(
            [
                User(id=user, telegram_user_id=user, username=f"test{user}", display_name="Test")
                for user in range(1, 5)
            ]
        )
    for user in range(1, 5):
        async with factory() as session:
            await WalletService(session).claim_welcome_grant(user, uuid4())
    clock = [datetime(2026, 10, 22, tzinfo=UTC)]

    def service(session):
        return BlackjackTableService(
            RoomService(session=session, now=lambda: clock[0], blackjack_rng=SeededRandomSource(9))
        )

    yield factory, service, clock
    await engine.dispose()


async def create(db, user=1, action_id=None):
    factory, service, _ = db
    async with factory() as session:
        return await service(session).create(user, action_id or uuid4())


async def join(db, snapshot, user, action_id=None):
    factory, service, _ = db
    async with factory() as session:
        return await service(session).join(snapshot.room_id, user, action_id or uuid4())


async def read(db, snapshot, user=1):
    factory, service, _ = db
    async with factory() as session, session.begin():
        room = await session.get(GameRoom, snapshot.room_id)
        return await service(session).project_snapshot(room, user)


async def move(db, snapshot, user, action, action_id=None, **payload):
    factory, service, _ = db
    async with factory() as session:
        return await service(session).apply(
            snapshot.room_id,
            user,
            ActionRequest(
                action_id=action_id or uuid4(),
                expected_state_version=snapshot.state_version,
                payload={"action": action, **payload},
            ),
        )


@pytest.mark.asyncio
async def test_three_members_fourth_rejected_and_join_replay(table_db):
    first = await create(table_db)
    assert first.public_state["phase"] == "lobby"
    second = await join(table_db, first, 2)
    await join(table_db, first, 3)
    again = await join(table_db, first, 2)
    assert len(again.public_state["players"]) == 3
    assert again.public_state["viewer_seat"] == second.public_state["viewer_seat"]
    with pytest.raises(RoomServiceError):
        await join(table_db, first, 4)
    with pytest.raises(RoomAccessError):
        await read(table_db, first, 4)


@pytest.mark.asyncio
async def test_full_round_ready_start_replay_and_next_round(table_db):
    first = await create(table_db)
    await join(table_db, first, 2)
    for user in (1, 2):
        snap = await read(table_db, first, user)
        await move(table_db, snap, user, "ready", bet=25)
    snap = await read(table_db, first)
    key = uuid4()
    event = await move(table_db, snap, 1, "start", action_id=key)
    replay = await move(table_db, snap, 1, "start", action_id=key)
    assert replay.event_id == event.event_id and replay.state_version == event.state_version
    with pytest.raises(RoomServiceError):
        await move(table_db, snap, 1, "ready", action_id=key, bet=50)
    for _ in range(3):
        snap = await read(table_db, first)
        if snap.public_state["phase"] == "settled":
            break
        seat = snap.public_state["active_seat"]
        actor = seat + 1
        await move(table_db, await read(table_db, first, actor), actor, "stand")
    done = await read(table_db, first)
    assert done.public_state["phase"] == "settled"
    assert all(not player["ready"] for player in done.public_state["players"])
    assert all(player["outcome"] for player in done.public_state["players"])
    factory, _, _ = table_db
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(GameRound)) == 1
    for user in (1, 2):
        await move(table_db, await read(table_db, first, user), user, "ready", bet=25)
    second = await move(table_db, await read(table_db, first), 1, "start")
    assert second.payload["public_state"]["round_id"] != done.public_state["round_id"]


@pytest.mark.asyncio
async def test_hidden_dealer_wrong_turn_deadline_restore_and_leave(table_db):
    first = await create(table_db)
    await join(table_db, first, 2)
    for user in (1, 2):
        await move(table_db, await read(table_db, first, user), user, "ready", bet=25)
    await move(table_db, await read(table_db, first), 1, "start")
    active = await read(table_db, first)
    assert active.public_state["dealer_cards"][1] == {"hidden": True}
    assert "deck" not in str(active.public_state)
    current = active.public_state["active_seat"] + 1
    other = 3 - current
    with pytest.raises(RoomServiceError):
        await move(table_db, await read(table_db, first, other), other, "hit")
    await move(table_db, await read(table_db, first, other), other, "leave")
    with pytest.raises(RoomAccessError):
        await read(table_db, first, other)
    factory, service, clock = table_db
    clock[0] += timedelta(seconds=21)
    with pytest.raises(RoomServiceError):
        await move(table_db, await read(table_db, first, current), current, "hit")
    async with factory() as session:
        assert await service(session).expire_due() == 1
    after = await read(table_db, first, current)
    assert after.state_version > active.state_version
    if after.public_state["phase"] != "settled":
        clock[0] += timedelta(seconds=21)
        async with factory() as session:
            await service(session).expire_due()
    done = await read(table_db, first, current)
    assert done.public_state["phase"] == "settled"
    assert len(done.public_state["players"]) == 1


@pytest.mark.asyncio
async def test_ready_never_charges_and_failed_start_is_atomic(table_db):
    first = await create(table_db)
    await join(table_db, first, 2)
    factory, _, _ = table_db
    for user in (1, 2):
        await move(table_db, await read(table_db, first, user), user, "ready", bet=1_000_000)
    with pytest.raises(RoomServiceError):
        await move(table_db, await read(table_db, first), 1, "start")
    assert (await read(table_db, first)).public_state["phase"] == "lobby"
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(GameRound)) == 0
    with pytest.raises(StateVersionConflictError):
        await move(table_db, first, 1, "unready")


@pytest.mark.asyncio
async def test_late_join_waits_for_next_round_and_old_event_stays_hidden(table_db):
    first = await create(table_db)
    await move(table_db, first, 1, "ready", bet=25)
    event = await move(table_db, await read(table_db, first), 1, "start")
    late = await join(table_db, first, 2)
    late_player = next(
        p for p in late.public_state["players"] if p["seat"] == late.public_state["viewer_seat"]
    )
    assert late_player["cards"] == [] and late_player["bet"] == 0
    assert late.public_state["legal_actions"] == ["leave"]
    with pytest.raises(RoomServiceError):
        await move(table_db, late, 2, "stand")
    await move(table_db, await read(table_db, first), 1, "stand")
    factory, service, _ = table_db
    async with factory() as session, session.begin():
        room = await session.get(GameRoom, first.room_id)
        projected = await service(session).project_event(room, event, 1)
        assert projected.payload["public_state"]["dealer_cards"][1] == {"hidden": True}
        stored = await session.get(GameAction, event.event_id)
        assert "deck" not in str(stored.payload_json)
        assert "wallet_balance" not in str(stored.payload_json)
    done = await read(table_db, first, 2)
    assert next(p for p in done.public_state["players"] if p["seat"] == 1)["outcome"] is None


@pytest.mark.asyncio
async def test_host_transfer_leave_replay_and_actor_collision(table_db):
    first = await create(table_db)
    await join(table_db, first, 2)
    old = await read(table_db, first)
    key = uuid4()
    event = await move(table_db, old, 1, "leave", action_id=key)
    replay = await move(table_db, old, 1, "leave", action_id=key)
    assert replay == event and replay.payload["public_state"]["phase"] == "left"
    second = await read(table_db, first, 2)
    assert second.public_state["host_seat"] == 1
    with pytest.raises(RoomServiceError):
        await move(table_db, second, 2, "leave", action_id=key)
    await join(table_db, first, 3)
    current = await read(table_db, first, 3)
    assert current.public_state["viewer_seat"] == 0
    assert current.public_state["host_seat"] == 1


@pytest.mark.asyncio
async def test_failed_double_preserves_deck_and_wallet(table_db):
    first = await create(table_db)
    await move(table_db, first, 1, "ready", bet=1000)
    await move(table_db, await read(table_db, first), 1, "start")
    before = await read(table_db, first)
    assert before.public_state["wallet_balance"] == 0
    factory, _, _ = table_db
    async with factory() as session:
        private_before = (await session.get(GameRoom, first.room_id)).private_state_json
    with pytest.raises(RoomServiceError):
        await move(table_db, before, 1, "double")
    after = await read(table_db, first)
    assert after == before
    async with factory() as session:
        assert (await session.get(GameRoom, first.room_id)).private_state_json == private_before


@pytest.mark.asyncio
async def test_last_payout_identity_conflict_rolls_back_entire_settlement(table_db):
    from uuid import UUID, uuid5

    from burmaldoza_domain.economy import LedgerReason
    from burmaldoza_domain.games.blackjack import Card

    class DealerBustRng:
        def shuffle(self, deck):
            top = [
                Card("10", "clubs"),
                Card("9", "clubs"),
                Card("10", "diamonds"),
                Card("9", "diamonds"),
                Card("10", "hearts"),
                Card("9", "hearts"),
                Card("10", "spades"),
                Card("6", "spades"),
                Card("K", "spades"),
            ]
            deck[:] = top + [card for card in deck if card not in top]

    first = await create(table_db)
    for user in (2, 3):
        await join(table_db, first, user)
    for user in (1, 2, 3):
        await move(table_db, await read(table_db, first, user), user, "ready", bet=25)
    factory, _, clock = table_db
    ready = await read(table_db, first)
    async with factory() as session:
        service = BlackjackTableService(
            RoomService(session=session, now=lambda: clock[0], blackjack_rng=DealerBustRng())
        )
        await service.apply(
            first.room_id,
            1,
            ActionRequest(
                action_id=uuid4(),
                expected_state_version=ready.state_version,
                payload={"action": "start"},
            ),
        )
    for user in (1, 2):
        await move(table_db, await read(table_db, first, user), user, "stand")
    before = await read(table_db, first, 3)
    round_id = UUID(before.public_state["round_id"])
    async with factory() as session:
        await WalletService(session).apply_delta(
            3, 1, LedgerReason.ADMIN_ADJUSTMENT, uuid4(), uuid5(round_id, "payout:3")
        )
    with pytest.raises(RoomServiceError, match="identity conflict"):
        await move(table_db, before, 3, "stand")
    after = await read(table_db, first, 3)
    assert after.state_version == before.state_version
    assert after.public_state["phase"] == "active"
    for user, expected in ((1, 975), (2, 975), (3, 976)):
        assert (await read(table_db, first, user)).public_state["wallet_balance"] == expected
    async with factory() as session:
        row = await session.get(GameRound, round_id)
        assert row.status == "active" and row.payout_amount == 0
