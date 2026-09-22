from __future__ import annotations

from uuid import uuid4

import pytest
from app.services.room_service import (
    MemoryRoomStore,
    RoomService,
    RoomServiceError,
)
from app.services.wallet_service import MemoryWalletStore, WalletService
from burmaldoza_contracts.common import GameType
from burmaldoza_contracts.rooms import ActionRequest, WebSocketAuthMessage
from burmaldoza_domain.core import StateVersionConflictError
from burmaldoza_domain.games.blackjack import Card

from tests.unit.test_telegram_auth import BOT_TOKEN, NOW, make_init_data


@pytest.mark.asyncio
async def test_room_action_is_idempotent_and_rejects_stale_version() -> None:
    wallet = WalletService(store=MemoryWalletStore())
    await wallet.claim_welcome_grant(12345, uuid4())
    service = RoomService(store=MemoryRoomStore(), wallet_service=wallet)
    created = await service.create_room(12345, GameType.SLOT, "solo")
    request = ActionRequest(
        action_id=uuid4(), expected_state_version=created.state_version, payload={"action": "spin"}
    )

    first = await service.apply_action(created.room_id, 12345, request)
    replay = await service.apply_action(created.room_id, 12345, request)

    assert replay == first
    assert first.state_version == created.state_version + 1
    assert (await service.snapshot(created.room_id, 12345)).state_version == first.state_version
    with pytest.raises(StateVersionConflictError):
        await service.apply_action(created.room_id, 12345, request.model_copy(update={"action_id": uuid4()}))


@pytest.mark.asyncio
async def test_slot_spin_persists_canonical_result_and_replays_without_respinning() -> None:
    wallet_store = MemoryWalletStore()
    wallet = WalletService(store=wallet_store)
    await wallet.claim_welcome_grant(12345, uuid4())

    class FixedStops:
        def __init__(self) -> None:
            self.calls = 0

        def randbelow(self, upper: int) -> int:
            assert upper == 10
            self.calls += 1
            return 0

    rng = FixedStops()
    service = RoomService(store=MemoryRoomStore(), wallet_service=wallet, slot_rng=rng)
    created = await service.create_room(12345, GameType.SLOT, "solo")
    request = ActionRequest(
        action_id=uuid4(), expected_state_version=created.state_version, payload={"action": "spin", "bet": 10}
    )

    first = await service.apply_action(created.room_id, 12345, request)
    replay = await service.apply_action(created.room_id, 12345, request)
    result = first.payload["result"]

    assert replay == first
    assert rng.calls == 3
    assert result["reel_stops"] == [0, 0, 0]
    assert len(result["grid"]) == 3
    assert result["grid"][0] == ["A", "A", "A", "B", "B", "C", "C"]
    assert result["winning_lines"][0]["rows"] == [3, 3, 3]
    assert result["gross_payout"] == 20
    assert result["net_delta"] == 10
    assert result["balance_after"] == 1010
    assert first.payload["public_state"]["last_result"] == result
    assert wallet_store.operation_count == 2
    assert wallet_store.ledger_entry_count == 3


@pytest.mark.asyncio
async def test_slot_zero_payout_is_persisted_without_a_payout_ledger_entry() -> None:
    wallet_store = MemoryWalletStore()
    wallet = WalletService(store=wallet_store)
    await wallet.claim_welcome_grant(12345, uuid4())

    class FixedStops:
        def __init__(self) -> None:
            self.values = iter((0, 0, 3))

        def randbelow(self, upper: int) -> int:
            assert upper == 10
            return next(self.values)

    service = RoomService(store=MemoryRoomStore(), wallet_service=wallet, slot_rng=FixedStops())
    created = await service.create_room(12345, GameType.SLOT, "solo")
    request = ActionRequest(
        action_id=uuid4(), expected_state_version=created.state_version, payload={"action": "spin", "bet": 10}
    )

    event = await service.apply_action(created.room_id, 12345, request)
    result = event.payload["result"]

    assert result["winning_lines"] == []
    assert result["gross_payout"] == 0
    assert result["net_delta"] == -10
    assert result["balance_after"] == 990
    assert wallet_store.operation_count == 2
    assert wallet_store.ledger_entry_count == 2


@pytest.mark.asyncio
async def test_memory_rejects_replaying_an_action_id_in_another_room() -> None:
    wallet_store = MemoryWalletStore()
    wallet = WalletService(store=wallet_store)
    await wallet.claim_welcome_grant(12345, uuid4())
    service = RoomService(store=MemoryRoomStore(), wallet_service=wallet)
    first_room = await service.create_room(12345, GameType.SLOT, "solo")
    second_room = await service.create_room(12345, GameType.SLOT, "solo")
    request = ActionRequest(
        action_id=uuid4(), expected_state_version=first_room.state_version, payload={"action": "spin", "bet": 10}
    )

    await service.apply_action(first_room.room_id, 12345, request)

    with pytest.raises(RoomServiceError, match="another room"):
        await service.apply_action(second_room.room_id, 12345, request)


@pytest.mark.asyncio
async def test_slot_spin_with_insufficient_balance_leaves_room_and_ledger_unchanged() -> None:
    wallet_store = MemoryWalletStore()
    wallet = WalletService(store=wallet_store)
    service = RoomService(store=MemoryRoomStore(), wallet_service=wallet)
    created = await service.create_room(12345, GameType.SLOT, "solo")
    request = ActionRequest(
        action_id=uuid4(), expected_state_version=created.state_version, payload={"action": "spin", "bet": 10}
    )

    with pytest.raises(RoomServiceError, match="insufficient"):
        await service.apply_action(created.room_id, 12345, request)

    snapshot = await service.snapshot(created.room_id, 12345)
    assert snapshot.state_version == created.state_version
    assert "last_result" not in snapshot.public_state
    assert wallet_store.operation_count == 0
    assert wallet_store.ledger_entry_count == 0


@pytest.mark.asyncio
async def test_snapshot_is_available_after_reconnect_and_auth_is_server_verified() -> None:
    wallet = WalletService(store=MemoryWalletStore())
    await wallet.claim_welcome_grant(12345, uuid4())
    service = RoomService(
        store=MemoryRoomStore(), wallet_service=wallet, bot_token=BOT_TOKEN, now=lambda: NOW
    )
    created = await service.create_room(12345, GameType.BLACKJACK, "solo")
    action = ActionRequest(
        action_id=uuid4(), expected_state_version=0, payload={"action": "deal", "bet": 25}
    )
    await service.apply_action(created.room_id, 12345, action)

    authenticated = await service.authenticate_websocket(
        WebSocketAuthMessage(type="auth", init_data=make_init_data())
    )
    reconnected = await service.snapshot(created.room_id, authenticated.user_id)

    assert authenticated.user_id == 12345
    assert reconnected.state_version == 1
    assert reconnected.public_state["last_action"] == "deal"
    assert reconnected.public_state["game_phase"] in {"player_turn", "dealer_resolution"}


@pytest.mark.asyncio
async def test_action_from_non_member_is_rejected() -> None:
    service = RoomService(store=MemoryRoomStore())
    created = await service.create_room(12345, GameType.HOLDEM, "heads-up")

    with pytest.raises(RoomServiceError, match="member"):
        await service.apply_action(
            created.room_id,
            54321,
            ActionRequest(action_id=uuid4(), expected_state_version=0, payload={"action": "check"}),
        )


class OrderedBlackjackRng:
    def __init__(self, top_cards: tuple[Card, ...]) -> None:
        self.top_cards = top_cards
        self.shuffle_calls = 0

    def randbelow(self, upper: int) -> int:
        raise AssertionError("blackjack does not use randbelow")

    def choice(self, sequence):
        raise AssertionError("blackjack does not use choice")

    def shuffle(self, values) -> None:
        self.shuffle_calls += 1
        values[:] = [*self.top_cards, *(card for card in values if card not in self.top_cards)]


def blackjack_rng(*cards: tuple[str, str]) -> OrderedBlackjackRng:
    return OrderedBlackjackRng(tuple(Card(rank, suit) for rank, suit in cards))


@pytest.mark.asyncio
async def test_blackjack_deal_hides_hole_card_and_retry_does_not_charge_or_shuffle_twice() -> None:
    wallet_store = MemoryWalletStore()
    wallet = WalletService(store=wallet_store)
    await wallet.claim_welcome_grant(12345, uuid4())
    rng = blackjack_rng(
        ("10", "clubs"), ("6", "clubs"), ("K", "diamonds"), ("6", "hearts"),
        ("5", "spades"), ("2", "spades"),
    )
    service = RoomService(store=MemoryRoomStore(), wallet_service=wallet, blackjack_rng=rng)
    room = await service.create_room(12345, GameType.BLACKJACK, "solo")
    deal = ActionRequest(
        action_id=uuid4(), expected_state_version=0, payload={"action": "deal", "bet": 25}
    )

    first = await service.apply_action(room.room_id, 12345, deal)
    replay = await service.apply_action(room.room_id, 12345, deal)

    assert replay == first
    assert first.payload["public_state"]["legal_actions"] == ["hit", "stand", "double"]
    assert first.payload["public_state"]["wallet_balance"] == 975
    assert first.payload["public_state"]["dealer_cards"] == [
        {"rank": "K", "suit": "diamonds"}, {"hidden": True}
    ]
    assert "dealer_total" not in first.payload["public_state"]
    assert (await wallet.get_or_create(12345)).balance == 975
    assert rng.shuffle_calls == 1
    assert wallet_store.ledger_entry_count == 2

    hit = ActionRequest(
        action_id=uuid4(), expected_state_version=1, payload={"action": "hit"}
    )
    won = await service.apply_action(room.room_id, 12345, hit)
    result = won.payload["result"]
    assert result["outcome"] == "win"
    assert result["gross_payout"] == 50
    assert result["net_delta"] == 25
    assert result["balance_after"] == 1025
    assert won.payload["public_state"]["dealer_cards"] == [
        {"rank": "K", "suit": "diamonds"}, {"rank": "6", "suit": "hearts"},
        {"rank": "2", "suit": "spades"},
    ]
    assert wallet_store.ledger_entry_count == 3


@pytest.mark.asyncio
async def test_blackjack_double_debits_incremental_stake_and_settles_once() -> None:
    wallet_store = MemoryWalletStore()
    wallet = WalletService(store=wallet_store)
    await wallet.claim_welcome_grant(22222, uuid4())
    rng = blackjack_rng(
        ("5", "clubs"), ("6", "clubs"), ("K", "diamonds"), ("7", "hearts"),
        ("8", "spades"),
    )
    service = RoomService(store=MemoryRoomStore(), wallet_service=wallet, blackjack_rng=rng)
    room = await service.create_room(22222, GameType.BLACKJACK, "solo")
    deal = ActionRequest(
        action_id=uuid4(), expected_state_version=0, payload={"action": "deal", "bet": 25}
    )
    await service.apply_action(room.room_id, 22222, deal)

    double = ActionRequest(
        action_id=uuid4(), expected_state_version=1, payload={"action": "double"}
    )
    first = await service.apply_action(room.room_id, 22222, double)
    replay = await service.apply_action(room.room_id, 22222, double)

    assert replay == first
    assert first.payload["result"]["outcome"] == "win"
    assert first.payload["result"]["gross_payout"] == 100
    assert first.payload["result"]["net_delta"] == 50
    assert first.payload["result"]["balance_after"] == 1050
    assert wallet_store.ledger_entry_count == 4
    assert rng.shuffle_calls == 1


@pytest.mark.asyncio
async def test_blackjack_natural_blackjack_uses_integer_three_to_two_gross_payout() -> None:
    wallet_store = MemoryWalletStore()
    wallet = WalletService(store=wallet_store)
    await wallet.claim_welcome_grant(33333, uuid4())
    rng = blackjack_rng(
        ("A", "clubs"), ("K", "clubs"), ("10", "diamonds"), ("7", "hearts"),
    )
    service = RoomService(store=MemoryRoomStore(), wallet_service=wallet, blackjack_rng=rng)
    room = await service.create_room(33333, GameType.BLACKJACK, "solo")
    action = ActionRequest(
        action_id=uuid4(), expected_state_version=0, payload={"action": "deal", "bet": 25}
    )

    event = await service.apply_action(room.room_id, 33333, action)

    assert event.payload["result"]["outcome"] == "blackjack"
    assert event.payload["result"]["gross_payout"] == 62
    assert event.payload["result"]["net_delta"] == 37
    assert event.payload["result"]["balance_after"] == 1037
    assert event.payload["public_state"]["dealer_hole_hidden"] is False


@pytest.mark.asyncio
async def test_blackjack_insufficient_balance_keeps_room_action_and_ledger_unchanged() -> None:
    wallet_store = MemoryWalletStore()
    service = RoomService(
        store=MemoryRoomStore(),
        wallet_service=WalletService(store=wallet_store),
        blackjack_rng=blackjack_rng(("10", "clubs")),
    )
    room = await service.create_room(44444, GameType.BLACKJACK, "solo")
    action = ActionRequest(
        action_id=uuid4(), expected_state_version=0, payload={"action": "deal", "bet": 25}
    )

    with pytest.raises(RoomServiceError, match="insufficient"):
        await service.apply_action(room.room_id, 44444, action)

    snapshot = await service.snapshot(room.room_id, 44444)
    assert snapshot.state_version == 0
    assert snapshot.public_state["legal_actions"] == ["deal"]
    assert wallet_store.operation_count == 0
    assert wallet_store.ledger_entry_count == 0


@pytest.mark.asyncio
async def test_blackjack_bet_must_match_published_ruleset_range() -> None:
    wallet_store = MemoryWalletStore()
    wallet = WalletService(store=wallet_store)
    await wallet.claim_welcome_grant(55555, uuid4())
    service = RoomService(store=MemoryRoomStore(), wallet_service=wallet)
    room = await service.create_room(55555, GameType.BLACKJACK, "solo")

    with pytest.raises(RoomServiceError, match="between 25 and 100"):
        await service.apply_action(
            room.room_id,
            55555,
            ActionRequest(
                action_id=uuid4(), expected_state_version=0, payload={"action": "deal", "bet": True}
            ),
        )
