from datetime import timedelta
from uuid import uuid4

import pytest
from app.db.models import User
from app.services.room_service import RoomService
from app.services.wallet_service import WalletService
from burmaldoza_contracts.common import GameType
from burmaldoza_contracts.rooms import ActionRequest
from burmaldoza_domain.games.slot_operations import ROTATION_START


@pytest.mark.asyncio
async def test_durable_spin_replay_keeps_operation_across_restart_and_week(session_factory):
    async with session_factory() as session, session.begin():
        session.add(User(id=1, telegram_user_id=1, display_name="Test"))
    async with session_factory() as session:
        await WalletService(session).claim_welcome_grant(1, uuid4())
    async with session_factory() as session:
        service = RoomService(session=session, now=lambda: ROTATION_START)
        room = await service.create_room(1, GameType.SLOT, "solo")
        request = ActionRequest(action_id=uuid4(), expected_state_version=0, payload={"action": "spin"})
        original = await service.apply_action(room.room_id, 1, request)
    async with session_factory() as session:
        service = RoomService(session=session, now=lambda: ROTATION_START + timedelta(days=7))
        snapshot = await service.snapshot(room.room_id, 1)
        assert snapshot.public_state["operation_id"] == "op2"
        assert snapshot.public_state["last_result"]["operation_id"] == "op1"
        before = (await WalletService(session).get_or_create(1)).balance
        assert await service.apply_action(room.room_id, 1, request) == original
        assert (await WalletService(session).get_or_create(1)).balance == before
        request = ActionRequest(action_id=uuid4(), expected_state_version=1, payload={"action":"spin"})
        next_spin = await service.apply_action(room.room_id, 1, request)
        assert next_spin.payload["result"]["operation_id"] == "op2"
