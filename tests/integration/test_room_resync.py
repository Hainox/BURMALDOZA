from __future__ import annotations

from uuid import uuid4

import pytest
from app.db.models import GameAction, GameRoom, LedgerEntry, User, WalletOperation
from app.services.event_bus import EventBus
from app.services.room_service import RoomService
from app.services.wallet_service import WalletService
from burmaldoza_contracts.common import GameType
from burmaldoza_contracts.rooms import ActionRequest
from burmaldoza_domain.economy import LedgerReason
from burmaldoza_domain.games.blackjack import Card
from sqlalchemy import func, select


@pytest.mark.asyncio
async def test_room_reconnect_reads_latest_snapshot_and_replay_does_not_duplicate_action(
    session_factory,
) -> None:
    user_id = 321
    action_id = uuid4()
    async with session_factory() as session:
        session.add(User(id=user_id, telegram_user_id=user_id, display_name="Test User"))
        await session.commit()
        service = RoomService(session=session, event_bus=EventBus())
        created = await service.create_room(user_id, GameType.HOLDEM, "heads-up")
        request = ActionRequest(
            action_id=action_id,
            expected_state_version=created.state_version,
            payload={"action": "check"},
        )
        first = await service.apply_action(created.room_id, user_id, request)

    async with session_factory() as session:
        reconnected_service = RoomService(session=session, event_bus=EventBus())
        snapshot = await reconnected_service.snapshot(created.room_id, user_id)
        replay = await reconnected_service.apply_action(created.room_id, user_id, request)
        action_count = await session.scalar(select(func.count(GameAction.id)))

    assert snapshot.state_version == first.state_version == 1
    assert snapshot.public_state["last_action"] == "check"
    assert replay == first
    assert action_count == 1


@pytest.mark.asyncio
async def test_slot_reconnect_preserves_server_result_and_wallet_replay(
    session_factory,
) -> None:
    user_id = 654
    action_id = uuid4()
    async with session_factory() as session:
        session.add(User(id=user_id, telegram_user_id=user_id, display_name="Slot User"))
        await session.commit()
        wallet = WalletService(session=session)
        await wallet.claim_welcome_grant(user_id, uuid4())
        service = RoomService(session=session, event_bus=EventBus(), wallet_service=wallet)
        created = await service.create_room(user_id, GameType.SLOT, "solo")
        request = ActionRequest(
            action_id=action_id,
            expected_state_version=created.state_version,
            payload={"action": "spin", "bet": 10},
        )
        first = await service.apply_action(created.room_id, user_id, request)

    async with session_factory() as session:
        reconnected_service = RoomService(session=session, event_bus=EventBus())
        snapshot = await reconnected_service.snapshot(created.room_id, user_id)
        replay = await reconnected_service.apply_action(created.room_id, user_id, request)
        operation_count = await session.scalar(select(func.count(WalletOperation.id)))

    assert snapshot.public_state["last_result"] == first.payload["result"]
    assert replay == first
    assert operation_count == 2


@pytest.mark.asyncio
async def test_blackjack_private_deal_and_settlement_survive_postgres_reconnect(
    session_factory,
) -> None:
    class OrderedBlackjackRng:
        def __init__(self) -> None:
            self.top_cards = (
                Card("10", "clubs"),
                Card("6", "clubs"),
                Card("K", "diamonds"),
                Card("6", "hearts"),
                Card("5", "spades"),
                Card("2", "spades"),
            )
            self.shuffle_calls = 0

        def randbelow(self, upper: int) -> int:
            raise AssertionError("blackjack does not use randbelow")

        def choice(self, sequence):
            raise AssertionError("blackjack does not use choice")

        def shuffle(self, values) -> None:
            self.shuffle_calls += 1
            values[:] = [*self.top_cards, *(card for card in values if card not in self.top_cards)]

    user_id = 876
    deal_id = uuid4()
    hit_id = uuid4()
    rng = OrderedBlackjackRng()
    async with session_factory() as session:
        session.add(User(id=user_id, telegram_user_id=user_id, display_name="Blackjack User"))
        await session.commit()
        wallet = WalletService(session=session)
        await wallet.claim_welcome_grant(user_id, uuid4())
        service = RoomService(
            session=session,
            event_bus=EventBus(),
            wallet_service=wallet,
            blackjack_rng=rng,
        )
        room = await service.create_room(user_id, GameType.BLACKJACK, "solo")
        deal = ActionRequest(
            action_id=deal_id,
            expected_state_version=0,
            payload={"action": "deal", "bet": 25},
        )
        dealt = await service.apply_action(room.room_id, user_id, deal)
        persisted = await session.get(GameRoom, room.room_id)
        raw_state = persisted.private_state_json

        assert dealt.payload["public_state"]["wallet_balance"] == 975
        assert dealt.payload["public_state"]["dealer_cards"] == [
            {"rank": "K", "suit": "diamonds"}, {"hidden": True}
        ]
        assert raw_state["blackjack_round"]["state"]["dealer_cards"][1] == {
            "rank": "6", "suit": "hearts"
        }
        assert "6" not in str(dealt.payload["public_state"]["dealer_cards"])
        await session.rollback()

        hit = ActionRequest(
            action_id=hit_id,
            expected_state_version=1,
            payload={"action": "hit"},
        )
        won = await service.apply_action(room.room_id, user_id, hit)

    async with session_factory() as session:
        service = RoomService(session=session, event_bus=EventBus())
        snapshot = await service.snapshot(room.room_id, user_id)
        replay = await service.apply_action(
            room.room_id,
            user_id,
            ActionRequest(
                action_id=hit_id,
                expected_state_version=1,
                payload={"action": "hit"},
            ),
        )
        action_count = await session.scalar(select(func.count(GameAction.id)))
        operation_count = await session.scalar(select(func.count(WalletOperation.id)))
        stake_entries = await session.scalar(
            select(func.count()).select_from(LedgerEntry).where(
                LedgerEntry.reason == LedgerReason.GAME_STAKE.value
            )
        )
        payout_entries = await session.scalar(
            select(func.count()).select_from(LedgerEntry).where(
                LedgerEntry.reason == LedgerReason.GAME_PAYOUT.value
            )
        )

    assert won.payload["result"]["outcome"] == "win"
    assert won.payload["result"]["gross_payout"] == 50
    assert snapshot.public_state["last_result"] == won.payload["result"]
    assert snapshot.public_state["dealer_hole_hidden"] is False
    assert replay == won
    assert rng.shuffle_calls == 1
    assert action_count == 2
    assert operation_count == 3
    assert stake_entries == 1
    assert payout_entries == 1
