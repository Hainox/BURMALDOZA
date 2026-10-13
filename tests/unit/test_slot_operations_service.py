from datetime import timedelta
from uuid import uuid4

import pytest
from app.core.config import Settings
from app.services.room_service import MemoryRoomStore, RoomService
from app.services.wallet_service import MemoryWalletStore, WalletService
from burmaldoza_contracts.common import GameType
from burmaldoza_contracts.rooms import ActionRequest
from burmaldoza_domain.games.slot_operations import ROTATION_START
from burmaldoza_domain.games.slot_ruleset import load_skeleton_config
from pydantic import ValidationError


def test_server_event_config_is_complete_and_aware():
    for values in (
        {"slot_event_operation_id": "arena"},
        {"slot_event_operation_id": "op1", "slot_event_starts_at": ROTATION_START, "slot_event_ends_at": ROTATION_START+timedelta(days=1)},
        {"slot_event_operation_id": "arena", "slot_event_starts_at": "2026-10-19T00:00:00", "slot_event_ends_at": "2026-10-20T00:00:00"},
    ):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **values)
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, bot_token="test-value-must-not-appear", slot_event_operation_id="arena")
    assert "test-value-must-not-appear" not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("skeleton", [False, True])
async def test_spin_freezes_operation_before_settlement_and_replay(skeleton):
    clock = [ROTATION_START + timedelta(days=7, microseconds=-1)]

    class CrossingWallet(WalletService):
        async def settle_game_round_in_transaction(self, *args, **kwargs):
            clock[0] += timedelta(seconds=2)
            return await super().settle_game_round_in_transaction(*args, **kwargs)

    wallet = CrossingWallet(store=MemoryWalletStore())
    await wallet.claim_welcome_grant(1, uuid4())
    service = RoomService(store=MemoryRoomStore(), wallet_service=wallet, now=lambda: clock[0], slot_config=load_skeleton_config() if skeleton else None)
    room = await service.create_room(1, GameType.SLOT, "solo")
    request = ActionRequest(action_id=uuid4(), expected_state_version=0, payload={"action":"spin"})
    first = await service.apply_action(room.room_id, 1, request)
    if skeleton:
        assert "operation_id" not in first.payload["result"]
        assert "operation_id" not in room.public_state
    else:
        assert room.public_state["operation_id"] == "op1"
        assert first.payload["result"]["operation_id"] == "op1"
        assert first.payload["public_state"]["operation_id"] == "op1"
        assert (await service.snapshot(room.room_id,1)).public_state["operation_id"] == "op2"
    assert await service.apply_action(room.room_id,1,request) == first
