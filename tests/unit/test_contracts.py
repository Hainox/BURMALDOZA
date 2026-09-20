from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from burmaldoza_contracts.common import GameType, RoomStatus
from burmaldoza_contracts.events import EventEnvelope
from burmaldoza_contracts.rooms import ActionRequest, RoomCreateRequest
from pydantic import ValidationError


def test_action_request_serializes_with_versioned_payload() -> None:
    action_id = uuid4()
    request = ActionRequest(
        action_id=action_id,
        expected_state_version=3,
        payload={"kind": "spin", "bet": 10},
    )

    assert request.action_id == action_id
    assert request.model_dump(mode="json") == {
        "action_id": str(action_id),
        "expected_state_version": 3,
        "payload": {"kind": "spin", "bet": 10},
    }


def test_event_envelope_contains_animation_hint_and_server_time() -> None:
    event_id = uuid4()
    room_id = uuid4()
    now = datetime(2026, 9, 20, tzinfo=UTC)
    event = EventEnvelope(
        event_id=event_id,
        room_id=room_id,
        state_version=4,
        type="slot.round.settled",
        ruleset_version="slot-skeleton-1",
        server_time=now,
        payload={"gross_payout": 20},
        animation_hint="slot.reels.stop.staggered",
    )

    assert event.model_dump(mode="json")["event_id"] == str(event_id)
    assert event.model_dump(mode="json")["room_id"] == str(room_id)
    assert event.animation_hint == "slot.reels.stop.staggered"


def test_action_request_rejects_invalid_version_and_empty_id() -> None:
    with pytest.raises(ValidationError):
        ActionRequest(action_id=uuid4(), expected_state_version=-1)
    with pytest.raises(ValidationError):
        ActionRequest(action_id="", expected_state_version=0)


def test_room_contracts_reject_unknown_game_type() -> None:
    room = RoomCreateRequest(game_type=GameType.SLOT, mode="practice")

    assert room.game_type is GameType.SLOT
    assert RoomStatus.WAITING.value == "waiting"

    with pytest.raises(ValidationError):
        RoomCreateRequest(game_type="roulette", mode="practice")


def test_room_contract_ids_are_uuid_values() -> None:
    request = ActionRequest(action_id=UUID(int=1), expected_state_version=0)

    assert request.action_id.int == 1
