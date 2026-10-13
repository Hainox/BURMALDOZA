from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.services.room_service import MemoryRoomStore, RoomService, RoomServiceError
from burmaldoza_contracts.common import GameType
from burmaldoza_contracts.rooms import RoomCreateRequest
from pydantic import ValidationError


def test_holdem_requires_explicit_supported_table_and_idempotency():
    for payload in (
        {"game_type": "holdem", "mode": "solo"},
        {"game_type": "holdem", "mode": "bot", "buy_in": True, "action_id": str(uuid4())},
        {"game_type": "holdem", "mode": "pvp", "buy_in": 100.0, "action_id": str(uuid4())},
    ):
        with pytest.raises(ValidationError):
            RoomCreateRequest.model_validate(payload)


@pytest.mark.asyncio
async def test_old_holdem_placeholder_cannot_charge_or_accept_moves():
    service = RoomService(store=MemoryRoomStore(), now=lambda: datetime.now(UTC))
    with pytest.raises(RoomServiceError):
        await service.create_room(42, GameType.HOLDEM, "heads-up")


import asyncio
from datetime import timedelta

import pytest_asyncio
from app.db.models import Base, GameAction, GamePlayer, GameRoom, HoldemHeroBag, LedgerEntry, User
from app.services.event_bus import EventBus
from app.services.holdem_service import _HERO_POOLS, HoldemService
from app.services.room_service import RoomAccessError
from app.services.wallet_service import WalletService
from burmaldoza_contracts.rooms import ActionRequest
from burmaldoza_domain.core import StateVersionConflictError
from burmaldoza_domain.rng import SeededRandomSource
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def holdem_db(tmp_path, monkeypatch):
    import app.services.holdem_service as module

    monkeypatch.setattr(module, "_QUEUE_LOCK", asyncio.Lock())
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'holdem.db').as_posix()}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as session, session.begin():
        session.add_all(
            [User(id=user, telegram_user_id=user, display_name="Test") for user in (1, 2, 3)]
        )
    for user in (1, 2, 3):
        async with factory() as session:
            await WalletService(session).claim_welcome_grant(user, uuid4())
    clock = [datetime(2026, 10, 13, tzinfo=UTC)]
    bus = EventBus()

    def service(session):
        return RoomService(
            session=session, event_bus=bus, now=lambda: clock[0], holdem_rng=SeededRandomSource(9)
        )

    yield factory, service, clock, bus
    await engine.dispose()


async def create(factory, service, user=1, mode="bot", buy_in=100, action_id=None):
    async with factory() as session:
        return await service(session).create_room(
            user, GameType.HOLDEM, mode, buy_in=buy_in, action_id=action_id or uuid4()
        )


async def move(factory, service, snapshot, user, action, action_id=None, **payload):
    async with factory() as session:
        return await service(session).apply_action(
            snapshot.room_id,
            user,
            ActionRequest(
                action_id=action_id or uuid4(),
                expected_state_version=snapshot.state_version,
                payload={"action": action, **payload},
            ),
        )


async def read(factory, service, room_id, user):
    async with factory() as session:
        return await service(session).snapshot(room_id, user)


@pytest.mark.asyncio
@pytest.mark.parametrize("buy_in", [100, 500, 1000])
async def test_bot_create_debits_once_replays_and_fold_never_exposes_enemy(holdem_db, buy_in):
    factory, service, _, bus = holdem_db
    action_id = uuid4()
    snapshot = await create(factory, service, buy_in=buy_in, action_id=action_id)
    assert snapshot.public_state["legal_actions"] == ["fold", "call", "raise"]
    assert snapshot.public_state["seat"] == 0
    assert snapshot.public_state["wallet_balance"] == 1000 - buy_in
    assert snapshot.public_state["hero_code"] in _HERO_POOLS[str(buy_in)]
    replay = await create(factory, service, buy_in=buy_in, action_id=action_id)
    assert replay == snapshot
    async with bus.subscribe(snapshot.room_id) as events:
        action_id = uuid4()
        event = await move(factory, service, snapshot, 1, "fold", action_id=action_id)
        public = await events.get()
        assert "hole_cards" not in str(public.payload)
        assert "deck" not in str(public.payload)
        assert event.payload["public_state"]["opponent_cards"] == [
            {"hidden": True},
            {"hidden": True},
        ]
        assert event.payload["result"]["payouts"][0] == buy_in - buy_in // 20
        assert event.payload["public_state"]["wallet_balance"] == 1000 - buy_in // 20
        assert await move(factory, service, snapshot, 1, "fold", action_id=action_id) == event
        with pytest.raises(RoomServiceError, match="different action"):
            await move(factory, service, snapshot, 1, "call", action_id=action_id)
    async with factory() as session:
        room = await session.get(GameRoom, snapshot.room_id)
        assert "hole_cards" not in str(room.state_json)
        assert "deck" not in str(room.state_json)
        assert len(room.private_state_json["state"]["hole_cards"][0]) == 2
        stakes = (
            await session.scalars(select(LedgerEntry).where(LedgerEntry.reason == "game_stake"))
        ).all()
        assert len(stakes) == 1 and stakes[0].amount_delta == -buy_in
        assert (
            await WalletService(session).get_or_create_in_transaction(1)
        ).balance == 1000 - buy_in // 20


@pytest.mark.asyncio
async def test_pvp_wait_match_reverse_seats_and_creation_identity(holdem_db):
    factory, service, _, _ = holdem_db
    key = uuid4()
    first = await create(factory, service, mode="pvp", action_id=key)
    assert first.status.value == "waiting"
    async with factory() as session:
        assert (await WalletService(session).get_or_create(1)).balance == 1000
    with pytest.raises(RoomServiceError, match="already searching"):
        await create(factory, service, mode="pvp")
    for user, mode, buy_in in [(2, "pvp", 100), (1, "bot", 100), (1, "pvp", 500)]:
        with pytest.raises(RoomServiceError, match="different action"):
            await create(factory, service, user=user, mode=mode, buy_in=buy_in, action_id=key)
    second = await create(factory, service, user=2, mode="pvp")
    assert second.room_id == first.room_id and second.public_state["seat"] == 1
    assert second.public_state["legal_actions"] == []
    first = await read(factory, service, first.room_id, 1)
    assert first.public_state["hole_cards"] != second.public_state["hole_cards"]
    assert second.public_state["opponent_cards"][0] == {"hidden": True}
    with pytest.raises(RoomAccessError):
        await read(factory, service, first.room_id, 3)
    with pytest.raises(RoomServiceError, match="out of turn"):
        await move(factory, service, second, 2, "fold")
    key = uuid4()
    event = await move(factory, service, first, 1, "call", action_id=key)
    with pytest.raises(RoomServiceError, match="different action"):
        await move(factory, service, first, 2, "call", action_id=key)
    with pytest.raises(StateVersionConflictError):
        await move(factory, service, first, 1, "call")
    second = await read(factory, service, first.room_id, 2)
    assert second.public_state["legal_actions"] == ["fold", "check", "raise"]
    assert event.state_version == second.state_version
    folded = await move(factory, service, second, 2, "fold")
    assert folded.payload["public_state"]["opponent_cards"] == [{"hidden": True}, {"hidden": True}]
    async with factory() as session:
        async with session.begin():
            wallets = [
                await WalletService(session).get_or_create_in_transaction(user) for user in (1, 2)
            ]
        assert sum(wallet.balance for wallet in wallets) == 2000


@pytest.mark.asyncio
async def test_timeouts_survive_fresh_service_and_expire_exactly_once(holdem_db):
    factory, service, clock, _ = holdem_db
    waiting = await create(factory, service, mode="pvp")
    clock[0] += timedelta(seconds=60)
    async with factory() as session:
        assert await HoldemService(service(session)).expire_due() == 1
    async with factory() as session:
        assert await HoldemService(service(session)).expire_due() == 0
        assert (await WalletService(session).get_or_create(1)).balance == 1000
    assert (await read(factory, service, waiting.room_id, 1)).status.value == "closed"
    first = await create(factory, service, mode="pvp")
    await create(factory, service, user=2, mode="pvp")
    first = await read(factory, service, first.room_id, 1)
    clock[0] += timedelta(seconds=20)
    with pytest.raises(RoomServiceError, match="deadline"):
        await move(factory, service, first, 1, "call")
    async with factory() as session:
        assert await HoldemService(service(session)).expire_due() == 1
    final = await read(factory, service, first.room_id, 1)
    assert final.public_state["last_result"]["outcome"] == "fold"
    assert final.public_state["opponent_cards"] == [{"hidden": True}, {"hidden": True}]
    async with factory() as session:
        assert await HoldemService(service(session)).expire_due() == 0
    # Check when the live big blind is not facing a bet.
    first = await create(factory, service, mode="pvp")
    await create(factory, service, user=2, mode="pvp")
    first = await read(factory, service, first.room_id, 1)
    await move(factory, service, first, 1, "call")
    clock[0] += timedelta(seconds=20)
    async with factory() as session:
        assert await HoldemService(service(session)).expire_due() == 1
    updated = await read(factory, service, first.room_id, 1)
    assert updated.public_state["game_phase"] == "flop"
    bot = await create(factory, service)
    clock[0] += timedelta(days=10)
    async with factory() as session:
        await HoldemService(service(session)).expire_due()
    assert (await read(factory, service, bot.room_id, 1)) == bot


@pytest.mark.asyncio
async def test_all_in_showdown_and_old_bus_events_do_not_leak(holdem_db):
    factory, service, clock, bus = holdem_db
    clock[0] = datetime.now(UTC)
    first = await create(factory, service, mode="pvp")
    await create(factory, service, user=2, mode="pvp")
    first = await read(factory, service, first.room_id, 1)
    async with bus.subscribe(first.room_id) as events:
        await move(factory, service, first, 1, "raise", amount=100)
        old = await events.get()
        second = await read(factory, service, first.room_id, 2)
        await move(factory, service, second, 2, "call")
        final_event = await events.get()
    async with factory() as session:
        old_seat1 = await service(session).personalize_event(old, 2)
        assert old_seat1.payload["public_state"]["opponent_cards"] == [
            {"hidden": True},
            {"hidden": True},
        ]
        final_seat1 = await service(session).personalize_event(final_event, 2)
        assert "rank" in final_seat1.payload["public_state"]["opponent_cards"][0]
        assert len(final_seat1.payload["public_state"]["community_cards"]) == 5
        assert sum(final_seat1.payload["result"]["payouts"]) == 200


@pytest.mark.asyncio
async def test_insufficient_matching_wallet_rolls_back_everything(holdem_db):
    factory, service, _, _ = holdem_db
    first = await create(factory, service, mode="pvp", buy_in=1000)
    await create(factory, service, user=2, buy_in=100)  # user2 only has900 after entering bot hand
    with pytest.raises(RoomServiceError, match="insufficient"):
        await create(factory, service, user=2, mode="pvp", buy_in=1000)
    assert (await read(factory, service, first.room_id, 1)).status.value == "waiting"
    async with factory() as session:
        assert (
            len(
                (
                    await session.scalars(
                        select(GamePlayer).where(GamePlayer.room_id == first.room_id)
                    )
                ).all()
            )
            == 1
        )
        assert (await WalletService(session).get_or_create_in_transaction(1)).balance == 1000


@pytest.mark.asyncio
async def test_hero_bag_is_persisted_no_repeats_until_exhaustion(holdem_db):
    factory, service, _, _ = holdem_db
    chosen = []
    for _ in range(111):
        async with factory() as session, session.begin():
            chosen.append(await HoldemService(service(session)).hero(1, 100))
    assert len(set(chosen[:110])) == 110
    assert chosen[110] in _HERO_POOLS["100"]
    async with factory() as session:
        bag = await session.get(HoldemHeroBag, (1, 100))
        assert len(bag.remaining_json) == 109


@pytest.mark.asyncio
@pytest.mark.parametrize("amount", [True, 100.0, "100", -1])
async def test_invalid_raise_has_no_effect(holdem_db, amount):
    factory, service, _, _ = holdem_db
    snapshot = await create(factory, service)
    with pytest.raises(RoomServiceError):
        await move(factory, service, snapshot, 1, "raise", amount=amount)
    assert (await read(factory, service, snapshot.room_id, 1)) == snapshot


@pytest.mark.asyncio
async def test_history_is_durable_paginated_and_contains_hero_only_for_owner(holdem_db):
    factory, service, _, _ = holdem_db
    first = await create(factory, service)
    await move(factory, service, first, 1, "fold")
    async with factory() as session:
        history = await HoldemService(service(session)).history(1, 1, 0)
    assert len(history) == 1
    assert history[0]["hero_code"] == first.public_state["hero_code"]
    assert history[0]["net_delta"] == -5
    assert "cards" not in str(history)
    async with factory() as session:
        assert await HoldemService(service(session)).history(2, 10, 0) == []
    async with factory() as session:
        assert await HoldemService(service(session)).history(1, 1, 1) == []


@pytest.mark.asyncio
async def test_corrupted_room_does_not_stop_other_timeouts(holdem_db, caplog):
    factory, service, clock, _ = holdem_db
    first = await create(factory, service, mode="pvp")
    await create(factory, service, user=2, mode="pvp")
    other = await create(factory, service, user=3, mode="pvp")
    async with factory() as session, session.begin():
        room = await session.get(GameRoom, first.room_id)
        room.private_state_json = {"state": {"corrupted": "do not log this private value"}}
    clock[0] += timedelta(seconds=60)
    async with factory() as session:
        assert await HoldemService(service(session)).expire_due() == 1
    assert (await read(factory, service, other.room_id, 3)).status.value == "closed"
    assert "holdem_deadline_room_failed" in caplog.text
    assert "do not log this private value" not in caplog.text


@pytest.mark.asyncio
async def test_http_holdem_privacy_replay_and_stale_conflict(holdem_db):
    from app.dependencies import CurrentUser, get_current_user, get_room_service
    from app.routers.rooms import router
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    factory, service, _, _ = holdem_db
    app = FastAPI()
    app.include_router(router)
    current = [1]
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        user_id=current[0], telegram_user_id=current[0], display_name="Test", username=None
    )

    async def get_service():
        async with factory() as session:
            yield service(session)

    app.dependency_overrides[get_room_service] = get_service
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/rooms",
            json={"game_type": "holdem", "mode": "pvp", "buy_in": 100, "action_id": str(uuid4())},
        )
        assert response.status_code == 200
        first = response.json()
        current[0] = 2
        second = (
            await client.post(
                "/api/v1/rooms",
                json={
                    "game_type": "holdem",
                    "mode": "pvp",
                    "buy_in": 100,
                    "action_id": str(uuid4()),
                },
            )
        ).json()
        assert second["public_state"]["seat"] == 1
        current[0] = 1
        first = (await client.get(f"/api/v1/rooms/{first['room_id']}")).json()
        body = {
            "action_id": str(uuid4()),
            "expected_state_version": first["state_version"],
            "payload": {"action": "call"},
        }
        response = await client.post(f"/api/v1/rooms/{first['room_id']}/actions", json=body)
        assert response.status_code == 200
        assert (
            response.json()["event"]["payload"]["public_state"]["hole_cards"]
            == first["public_state"]["hole_cards"]
        )
        response = await client.post(
            f"/api/v1/rooms/{first['room_id']}/actions", json={**body, "action_id": str(uuid4())}
        )
        assert response.status_code == 409
        assert response.json()["detail"]["snapshot"]["public_state"]["seat"] == 0
        assert response.json()["detail"]["snapshot"]["public_state"]["opponent_cards"] == [
            {"hidden": True},
            {"hidden": True},
        ]
        current[0] = 3
        assert (await client.get(f"/api/v1/rooms/{first['room_id']}")).status_code == 403
        assert (await client.get("/api/v1/holdem/history")).json()["items"] == []
        assert (await client.get("/api/v1/holdem/history?limit=101")).status_code == 422


@pytest.mark.asyncio
async def test_websocket_snapshots_events_are_personalized_and_nonmembers_rejected(holdem_db):
    from app.core.config import Settings
    from app.db.session import get_session
    from app.routers.rooms import router
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from tests.unit.test_telegram_auth import BOT_TOKEN, make_init_data

    factory, service, clock, bus = holdem_db
    clock[0] = datetime.now(UTC)
    first = await create(factory, service, mode="pvp")
    await create(factory, service, user=2, mode="pvp")
    app = FastAPI()
    app.include_router(router)
    app.state.settings = Settings(bot_token=BOT_TOKEN)
    app.state.session_factory = factory
    app.state.event_bus = bus

    async def session_dep():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = session_dep
    raw = {
        user: make_init_data(auth_date=datetime.now(UTC), user={"id": user, "first_name": "Test"})
        for user in (1, 2, 3)
    }
    with TestClient(app) as client:
        with client.websocket_connect(f"/api/v1/rooms/{first.room_id}/events") as ws1:
            ws1.send_json({"type": "auth", "init_data": raw[1]})
            own1 = ws1.receive_json()["snapshot"]
            with client.websocket_connect(f"/api/v1/rooms/{first.room_id}/events") as ws2:
                ws2.send_json({"type": "auth", "init_data": raw[2]})
                own2 = ws2.receive_json()["snapshot"]
                assert own1["public_state"]["hole_cards"] != own2["public_state"]["hole_cards"]
                response = client.post(
                    f"/api/v1/rooms/{first.room_id}/actions",
                    headers={"X-Telegram-Init-Data": raw[1]},
                    json={
                        "action_id": str(uuid4()),
                        "expected_state_version": own1["state_version"],
                        "payload": {"action": "fold"},
                    },
                )
                assert response.status_code == 200
                event1 = ws1.receive_json()["event"]
                event2 = ws2.receive_json()["event"]
                assert (
                    event1["payload"]["public_state"]["hole_cards"]
                    == own1["public_state"]["hole_cards"]
                )
                assert (
                    event2["payload"]["public_state"]["hole_cards"]
                    == own2["public_state"]["hole_cards"]
                )
                assert event2["payload"]["public_state"]["opponent_cards"] == [
                    {"hidden": True},
                    {"hidden": True},
                ]
        from starlette.websockets import WebSocketDisconnect

        with (
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect(f"/api/v1/rooms/{first.room_id}/events") as ws,
        ):
            ws.send_json({"type": "auth", "init_data": raw[3]})
            ws.receive_json()


@pytest.mark.asyncio
async def test_lifespan_cancels_timer_and_tick_failure_recovers(monkeypatch):
    from contextlib import asynccontextmanager

    from app import main
    from app.main import _holdem_timer, lifespan
    from fastapi import FastAPI

    application = FastAPI()
    cancelled = asyncio.Event()
    started = asyncio.Event()

    async def timer(app):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr(main, "_holdem_timer", timer)
    async with lifespan(application):
        await asyncio.wait_for(started.wait(), 1)
    assert cancelled.is_set()

    @asynccontextmanager
    async def factory():
        yield None

    application.state.session_factory = factory
    application.state.event_bus = EventBus()
    calls = []
    recovered = asyncio.Event()

    async def tick(self):
        calls.append(1)
        if len(calls) == 1:
            raise ValueError("private details must not appear in log")
        recovered.set()

    monkeypatch.setattr(HoldemService, "expire_due", tick)
    task = asyncio.create_task(_holdem_timer(application))
    try:
        await asyncio.wait_for(recovered.wait(), 7)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_tie_refunds_both_full_stacks_and_bot_hand_completes(holdem_db):
    from dataclasses import replace

    from app.services.holdem_service import decode_state, encode_state
    from burmaldoza_domain.games.blackjack import Card, make_deck

    factory, service, _, _ = holdem_db
    first = await create(factory, service, mode="pvp")
    await create(factory, service, user=2, mode="pvp")
    board = tuple(Card(rank, "S") for rank in ("10", "J", "Q", "K", "A"))
    holes = ((Card("2", "C"), Card("3", "D")), (Card("4", "C"), Card("5", "D")))
    excluded = set(board + holes[0] + holes[1])
    async with factory() as session, session.begin():
        room = await session.get(GameRoom, first.room_id)
        state = decode_state(room.private_state_json["state"])
        state = replace(
            state,
            hole_cards=holes,
            deck=board + tuple(card for card in make_deck() if card not in excluded),
        )
        room.private_state_json = {**room.private_state_json, "state": encode_state(state)}
    first = await read(factory, service, first.room_id, 1)
    await move(factory, service, first, 1, "raise", amount=100)
    second = await read(factory, service, first.room_id, 2)
    settled = await move(factory, service, second, 2, "call")
    assert settled.payload["result"]["payouts"] == [100, 100]
    assert settled.payload["result"]["net_deltas"] == [0, 0]
    bot = await create(factory, service, user=3)
    for _ in range(30):
        if bot.status.value == "settled":
            break
        action = "check" if "check" in bot.public_state["legal_actions"] else "call"
        await move(factory, service, bot, 3, action)
        bot = await read(factory, service, bot.room_id, 3)
    assert bot.status.value == "settled"
    assert bot.public_state["last_result"]["outcome"] in ("fold", "showdown")


@pytest.mark.asyncio
@pytest.mark.parametrize("purpose", ["stake", "payout"])
async def test_foreign_grant_at_derived_game_key_cannot_replace_game_ledger(holdem_db, purpose):
    from uuid import NAMESPACE_URL, uuid5

    from app.db.models import GameRound

    factory, service, _, _ = holdem_db
    key = uuid4()
    snapshot = None
    if purpose == "payout":
        snapshot = await create(factory, service)
    collision = uuid5(NAMESPACE_URL, f"holdem:{key}:{purpose}:1")
    async with factory() as session:
        grant = await WalletService(session).claim_daily_bonus(1, datetime.now(UTC), collision)
    async with factory() as session:
        before = (await WalletService(session).get_or_create(1)).balance
    with pytest.raises(RoomServiceError, match="ledger"):
        if purpose == "stake":
            await create(factory, service, action_id=key)
        else:
            await move(factory, service, snapshot, 1, "fold", action_id=key)
    async with factory() as session:
        assert (await WalletService(session).get_or_create(1)).balance == before
    async with factory() as session:
        entries = (await session.scalars(select(LedgerEntry))).all()
        assert any(
            entry.operation_id == grant.operation_id and entry.reason == "daily_bonus"
            for entry in entries
        )
        assert sum(entry.reason == "game_payout" for entry in entries) == 0
        assert sum(entry.reason == "game_stake" for entry in entries) == (
            1 if purpose == "payout" else 0
        )
        assert await session.scalar(select(func.count()).select_from(GameRound)) == (
            1 if purpose == "payout" else 0
        )
    if snapshot:
        # Fresh ID still finishes the original unchanged hand.
        assert (await read(factory, service, snapshot.room_id, 1)).status.value == "active"
        await move(factory, service, snapshot, 1, "fold")
    else:
        await create(factory, service)


@pytest.mark.asyncio
async def test_insolvent_queue_candidate_is_cancelled_and_does_not_poison_matching(holdem_db):
    from app.db.models import Wallet

    factory, service, _, _ = holdem_db
    async with factory() as session, session.begin():
        wallet = await session.get(Wallet, 3)
        wallet.balance = 0
    with pytest.raises(RoomServiceError, match="insufficient"):
        await create(factory, service, user=3, mode="pvp")
    first = await create(factory, service, user=1, mode="pvp")
    async with factory() as session, session.begin():
        wallet = await session.get(Wallet, 1)
        wallet.balance = 0
    funded = await create(factory, service, user=2, mode="pvp")
    assert funded.status.value == "waiting"
    assert (await read(factory, service, first.room_id, 1)).status.value == "closed"
    async with factory() as session, session.begin():
        wallet = await session.get(Wallet, 3)
        wallet.balance = 1000
    joined = await create(factory, service, user=3, mode="pvp")
    assert joined.room_id == funded.room_id and joined.status.value == "active"
    async with factory() as session:
        stakes = (
            await session.scalars(select(LedgerEntry).where(LedgerEntry.reason == "game_stake"))
        ).all()
        assert {entry.wallet_id for entry in stakes} == {2, 3}


@pytest.mark.asyncio
@pytest.mark.parametrize("purpose", ["stake", "payout"])
async def test_second_pvp_wallet_collision_rolls_back_first_wallet_delta(holdem_db, purpose):
    from uuid import NAMESPACE_URL, uuid5

    factory, service, _, _ = holdem_db
    first = await create(factory, service, mode="pvp")
    key = uuid4()
    if purpose == "payout":
        await create(factory, service, user=2, mode="pvp")
        first = await read(factory, service, first.room_id, 1)
    collision = uuid5(NAMESPACE_URL, f"holdem:{key}:{purpose}:2")
    async with factory() as session:
        await WalletService(session).claim_daily_bonus(2, datetime.now(UTC), collision)
    async with factory() as session:
        before1 = (await WalletService(session).get_or_create(1)).balance
    async with factory() as session:
        before2 = (await WalletService(session).get_or_create(2)).balance
    with pytest.raises(RoomServiceError, match="ledger"):
        if purpose == "stake":
            await create(factory, service, user=2, mode="pvp", action_id=key)
        else:
            await move(factory, service, first, 1, "fold", action_id=key)
    async with factory() as session:
        assert (await WalletService(session).get_or_create(1)).balance == before1
    async with factory() as session:
        assert (await WalletService(session).get_or_create(2)).balance == before2
    async with factory() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(LedgerEntry)
                .where(LedgerEntry.reason == "game_payout")
            )
            == 0
        )
        assert await session.get(GameAction, key) is None
    first = await read(factory, service, first.room_id, 1)
    assert first.status.value == ("waiting" if purpose == "stake" else "active")
    if purpose == "stake":
        await create(factory, service, user=2, mode="pvp")
    else:
        await move(factory, service, first, 1, "fold")


@pytest.mark.asyncio
async def test_search_cancel_is_durable_idempotent_and_cannot_cancel_matched_hand(holdem_db):
    factory, service, _, bus = holdem_db
    waiting = await create(factory, service, mode="pvp")
    key = uuid4()
    async with bus.subscribe(waiting.room_id) as events:
        cancelled = await move(factory, service, waiting, 1, "cancel", action_id=key)
        assert cancelled.payload["public_state"]["phase"] == "cancelled"
        assert cancelled.payload["public_state"]["search_deadline"] is None
        assert await events.get()
        assert await move(factory, service, waiting, 1, "cancel", action_id=key) == cancelled
        assert events.empty()
    assert (await read(factory, service, waiting.room_id, 1)).status.value == "closed"
    async with factory() as session:
        assert (await WalletService(session).get_or_create(1)).balance == 1000
    other = await create(factory, service, user=2, mode="pvp")
    assert other.room_id != waiting.room_id
    joined = await create(factory, service, mode="pvp")
    assert joined.room_id == other.room_id
    with pytest.raises(RoomServiceError):
        await move(factory, service, joined, 1, "cancel")
    assert (await read(factory, service, joined.room_id, 1)).status.value == "active"
