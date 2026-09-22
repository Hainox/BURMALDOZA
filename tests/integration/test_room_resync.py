from __future__ import annotations

from uuid import uuid4

import pytest
from app.db.models import GameAction, User, WalletOperation
from app.services.event_bus import EventBus
from app.services.room_service import RoomService
from app.services.wallet_service import WalletService
from burmaldoza_contracts.common import GameType
from burmaldoza_contracts.rooms import ActionRequest
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
