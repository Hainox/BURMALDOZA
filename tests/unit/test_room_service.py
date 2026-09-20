from __future__ import annotations

from uuid import uuid4

import pytest
from app.services.room_service import (
    MemoryRoomStore,
    RoomService,
    RoomServiceError,
)
from burmaldoza_contracts.common import GameType
from burmaldoza_contracts.rooms import ActionRequest, WebSocketAuthMessage
from burmaldoza_domain.core import StateVersionConflictError

from tests.unit.test_telegram_auth import BOT_TOKEN, NOW, make_init_data


@pytest.mark.asyncio
async def test_room_action_is_idempotent_and_rejects_stale_version() -> None:
    service = RoomService(store=MemoryRoomStore())
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
