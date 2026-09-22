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
    service = RoomService(store=MemoryRoomStore(), bot_token=BOT_TOKEN, now=lambda: NOW)
    created = await service.create_room(12345, GameType.BLACKJACK, "solo")
    action = ActionRequest(
        action_id=uuid4(), expected_state_version=0, payload={"action": "stand"}
    )
    await service.apply_action(created.room_id, 12345, action)

    authenticated = await service.authenticate_websocket(
        WebSocketAuthMessage(type="auth", init_data=make_init_data())
    )
    reconnected = await service.snapshot(created.room_id, authenticated.user_id)

    assert authenticated.user_id == 12345
    assert reconnected.state_version == 1
    assert reconnected.public_state["last_action"] == "stand"


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
