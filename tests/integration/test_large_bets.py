import asyncio
from uuid import uuid4

import pytest
from app.db.models import GameAction, LedgerEntry, User, Wallet
from app.services.room_service import RoomService, RoomServiceError
from app.services.wallet_service import WalletService
from burmaldoza_contracts.common import GameType
from burmaldoza_contracts.rooms import ActionRequest
from burmaldoza_domain.economy import LedgerReason
from sqlalchemy import func, select

from tests.unit.test_room_service import blackjack_rng


class MaximumSiegeStops:
    def __init__(self):
        self.stops = iter((15, 16, 17))

    def randbelow(self, upper):
        assert upper == 30
        return next(self.stops)


async def fund(session_factory, balance):
    async with session_factory() as session, session.begin():
        session.add(User(id=1, telegram_user_id=1, display_name="Test"))
    async with session_factory() as session:
        await WalletService(session).apply_delta(
            1, balance, LedgerReason.ADMIN_ADJUSTMENT, uuid4(), uuid4()
        )


@pytest.mark.asyncio
async def test_maximum_slot_payout_above_int32_is_durable_and_replayed(session_factory):
    await fund(session_factory, 2_100_000_000)
    async with session_factory() as session:
        service = RoomService(session=session, slot_rng=MaximumSiegeStops())
        room = await service.create_room(1, GameType.SLOT, "solo")
        request = ActionRequest(action_id=uuid4(), expected_state_version=0,
                                payload={"action": "spin", "bet": 1_000_000})
        event = await service.apply_action(room.room_id, 1, request)
        assert event.payload["result"]["gross_payout"] == 72_000_000
        assert event.payload["result"]["balance_after"] == 2_171_000_000
    async with session_factory() as session:
        replay = await RoomService(session=session).apply_action(room.room_id, 1, request)
        assert replay == event
        assert (await WalletService(session).get_or_create(1)).balance == 2_171_000_000
        entries = (await session.scalars(select(LedgerEntry))).all()
        assert len(entries) == 3
        assert max(entry.balance_after for entry in entries) == 2_171_000_000


@pytest.mark.asyncio
async def test_concurrent_whole_balance_bets_and_unfunded_double(session_factory):
    await fund(session_factory, 1_000_000)
    rooms = []
    async with session_factory() as session:
        service = RoomService(session=session)
        for _ in range(2):
            rooms.append(await service.create_room(1, GameType.BLACKJACK, "solo"))

    async def deal(room):
        async with session_factory() as session:
            service = RoomService(session=session, blackjack_rng=blackjack_rng(
                ("5", "clubs"), ("6", "clubs"), ("K", "diamonds"), ("7", "hearts"),
                ("8", "spades")))
            try:
                return room, await service.apply_action(room.room_id, 1, ActionRequest(
                    action_id=uuid4(), expected_state_version=0,
                    payload={"action": "deal", "bet": 1_000_000}))
            except RoomServiceError as error:
                assert "insufficient balance" in str(error)
                return room, error

    attempts = await asyncio.gather(*(deal(room) for room in rooms))
    accepted = [(room, event) for room, event in attempts if not isinstance(event, Exception)]
    assert len(accepted) == 1
    room, _ = accepted[0]
    async with session_factory() as session:
        service = RoomService(session=session, blackjack_rng=blackjack_rng(("8", "spades")))
        before = await service.snapshot(room.room_id, 1)
        with pytest.raises(RoomServiceError, match="insufficient balance for blackjack double"):
            await service.apply_action(room.room_id, 1, ActionRequest(
                action_id=uuid4(), expected_state_version=1, payload={"action": "double"}))
        assert await service.snapshot(room.room_id, 1) == before
        assert (await WalletService(session).get_or_create(1)).balance == 0
        assert await session.scalar(select(func.count()).select_from(GameAction)) == 1
        assert await session.scalar(select(func.count()).select_from(LedgerEntry)) == 2
        assert (await session.get(Wallet, 1)).balance == 0
