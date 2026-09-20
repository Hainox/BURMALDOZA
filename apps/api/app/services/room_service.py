from __future__ import annotations

import asyncio
import copy
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from burmaldoza_contracts.common import GameType, RoomStatus
from burmaldoza_contracts.events import EventEnvelope
from burmaldoza_contracts.rooms import ActionRequest, RoomSnapshot, WebSocketAuthMessage
from burmaldoza_domain.core import StateVersionConflictError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.telegram_auth import TelegramAuthError, verify_telegram_init_data
from app.db.models import GameAction, GamePlayer, GameRoom, User
from app.dependencies import CurrentUser
from app.services.event_bus import EventBus


class RoomServiceError(ValueError):
    """Base error for room access and action validation failures."""


class RoomNotFoundError(RoomServiceError):
    """Raised when a room does not exist."""


class RoomAccessError(RoomServiceError):
    """Raised when a user is not a member of a room."""


@dataclass(slots=True)
class _MemoryRoom:
    room_id: UUID
    owner_id: int
    game_type: GameType
    mode: str
    status: RoomStatus
    ruleset_version: str
    state_version: int = 0
    public_state: dict[str, Any] = field(default_factory=dict)
    members: set[int] = field(default_factory=set)
    actions: dict[UUID, EventEnvelope] = field(default_factory=dict)


class MemoryRoomStore:
    """Deterministic room store for API/unit tests; production uses PostgreSQL."""

    def __init__(self) -> None:
        self.rooms: dict[UUID, _MemoryRoom] = {}


_RULESET_VERSIONS = {
    GameType.SLOT: "slot-skeleton-1",
    GameType.BLACKJACK: "blackjack-gfl-skeleton-1",
    GameType.HOLDEM: "holdem-skeleton-1",
}
_LEGAL_ACTIONS = {
    GameType.SLOT: ("spin",),
    GameType.BLACKJACK: ("hit", "stand", "double"),
    GameType.HOLDEM: ("fold", "check", "call", "raise"),
}
_ANIMATION_HINTS = {
    GameType.SLOT: "slot.reels.stop.staggered",
    GameType.BLACKJACK: "blackjack.cards.deal.staged",
    GameType.HOLDEM: "holdem.action.confirmed",
}


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _safe_json(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _initial_public_state(game_type: GameType) -> dict[str, Any]:
    return {
        "phase": "waiting",
        "legal_actions": list(_LEGAL_ACTIONS[game_type]),
        "action_count": 0,
    }


def _action_name(request: ActionRequest, game_type: GameType) -> str:
    raw_action = request.payload.get("action", request.payload.get("type"))
    if not isinstance(raw_action, str):
        raise RoomServiceError("action payload must include a string action")
    action = raw_action.lower().strip()
    if action not in _LEGAL_ACTIONS[game_type]:
        raise RoomServiceError(f"action {action!r} is not legal for {game_type.value}")
    if game_type is GameType.SLOT and "bet" in request.payload:
        bet = request.payload["bet"]
        if isinstance(bet, bool) or not isinstance(bet, int) or not 10 <= bet <= 100:
            raise RoomServiceError("slot bet must be an integer between 10 and 100")
    return action


def _snapshot_from_memory(room: _MemoryRoom) -> RoomSnapshot:
    return RoomSnapshot(
        room_id=room.room_id,
        game_type=room.game_type,
        mode=room.mode,
        status=room.status,
        ruleset_version=room.ruleset_version,
        state_version=room.state_version,
        public_state=copy.deepcopy(room.public_state),
    )


class RoomService:
    def __init__(
        self,
        session: AsyncSession | None = None,
        *,
        store: MemoryRoomStore | None = None,
        event_bus: EventBus | None = None,
        bot_token: str = "",
        max_auth_age_seconds: int = 86400,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if session is not None and store is not None:
            raise ValueError("provide either session or store")
        self.session = session
        self.store = store if store is not None else (None if session is not None else MemoryRoomStore())
        self.event_bus = event_bus or EventBus()
        self.bot_token = bot_token
        self.max_auth_age_seconds = max_auth_age_seconds
        self.now = now or (lambda: datetime.now(UTC))
        self._lock = asyncio.Lock()

    async def create_room(self, user_id: int, game_type: GameType, mode: str) -> RoomSnapshot:
        try:
            game_type = GameType(game_type)
        except ValueError as error:
            raise RoomServiceError("unknown game type") from error
        if not mode or len(mode) > 32:
            raise RoomServiceError("room mode is invalid")
        ruleset_version = _RULESET_VERSIONS[game_type]
        public_state = _initial_public_state(game_type)

        if self.store is not None:
            async with self._lock:
                room = _MemoryRoom(
                    room_id=uuid4(),
                    owner_id=user_id,
                    game_type=game_type,
                    mode=mode,
                    status=RoomStatus.WAITING,
                    ruleset_version=ruleset_version,
                    public_state=public_state,
                    members={user_id},
                )
                self.store.rooms[room.room_id] = room
                return _snapshot_from_memory(room)

        assert self.session is not None
        async with self.session.begin():
            room = GameRoom(
                game_type=game_type.value,
                mode=mode,
                status=RoomStatus.WAITING.value,
                ruleset_version=ruleset_version,
                state_version=0,
                state_json=public_state,
            )
            self.session.add(room)
            await self.session.flush()
            self.session.add(GamePlayer(room_id=room.id, user_id=user_id, seat=0, stack=0))
            await self.session.flush()
            return self._db_snapshot(room)

    async def snapshot(self, room_id: UUID, user_id: int) -> RoomSnapshot:
        if self.store is not None:
            async with self._lock:
                room = self._get_memory_room(room_id)
                self._require_member(room, user_id)
                return _snapshot_from_memory(room)

        assert self.session is not None
        async with self.session.begin():
            room = await self._load_db_room(room_id, lock=False)
            await self._require_db_member(room_id, user_id)
            return self._db_snapshot(room)

    async def apply_action(self, room_id: UUID, user_id: int, request: ActionRequest) -> EventEnvelope:
        if self.store is not None:
            async with self._lock:
                room = self._get_memory_room(room_id)
                self._require_member(room, user_id)
                replay = room.actions.get(request.action_id)
                if replay is not None:
                    return replay
                if request.expected_state_version != room.state_version:
                    raise StateVersionConflictError(
                        f"expected state_version {request.expected_state_version}, current is {room.state_version}"
                    )
                action = _action_name(request, room.game_type)
                event = self._advance_memory(room, request, action)
            await self.event_bus.publish(event)
            return event

        assert self.session is not None
        event: EventEnvelope
        async with self.session.begin():
            room = await self._load_db_room(room_id, lock=True)
            await self._require_db_member(room_id, user_id)
            action_row = (
                await self.session.execute(select(GameAction).where(GameAction.id == request.action_id))
            ).scalar_one_or_none()
            if action_row is not None:
                if action_row.room_id != room_id:
                    raise RoomServiceError("action_id already belongs to another room")
                event = self._event_from_action(room, action_row)
            else:
                if request.expected_state_version != room.state_version:
                    raise StateVersionConflictError(
                        f"expected state_version {request.expected_state_version}, current is {room.state_version}"
                    )
                action = _action_name(request, GameType(room.game_type))
                event = self._advance_db(room, user_id, request, action)
        await self.event_bus.publish(event)
        return event

    async def authenticate_websocket(self, first_message: WebSocketAuthMessage) -> CurrentUser:
        try:
            message = (
                first_message
                if isinstance(first_message, WebSocketAuthMessage)
                else WebSocketAuthMessage.model_validate(first_message)
            )
            context = verify_telegram_init_data(
                message.init_data,
                self.bot_token,
                _utc(self.now()),
                self.max_auth_age_seconds,
            )
        except (TelegramAuthError, ValueError) as error:
            raise RoomServiceError("invalid WebSocket authentication") from error

        if self.session is None:
            return CurrentUser(
                user_id=context.telegram_user_id,
                telegram_user_id=context.telegram_user_id,
                display_name=context.display_name,
                username=context.username,
            )

        async with self.session.begin():
            user = (
                await self.session.execute(
                    select(User).where(User.telegram_user_id == context.telegram_user_id)
                )
            ).scalar_one_or_none()
            if user is None:
                user = User(
                    telegram_user_id=context.telegram_user_id,
                    display_name=context.display_name,
                )
                self.session.add(user)
                await self.session.flush()
            else:
                user.display_name = context.display_name
                await self.session.flush()
        return CurrentUser(
            user_id=user.id,
            telegram_user_id=context.telegram_user_id,
            display_name=context.display_name,
            username=context.username,
        )

    def _get_memory_room(self, room_id: UUID) -> _MemoryRoom:
        assert self.store is not None
        room = self.store.rooms.get(room_id)
        if room is None:
            raise RoomNotFoundError("room not found")
        return room

    @staticmethod
    def _require_member(room: _MemoryRoom, user_id: int) -> None:
        if user_id not in room.members:
            raise RoomAccessError("user is not a room member")

    def _advance_memory(self, room: _MemoryRoom, request: ActionRequest, action: str) -> EventEnvelope:
        room.state_version += 1
        room.status = RoomStatus.ACTIVE
        room.public_state = self._next_public_state(room.public_state, request, action)
        event = self._build_event(
            room.room_id,
            room.state_version,
            room.game_type,
            request.action_id,
            room.public_state,
        )
        room.actions[request.action_id] = event
        return event

    def _next_public_state(
        self, current: dict[str, Any], request: ActionRequest, action: str
    ) -> dict[str, Any]:
        next_state = copy.deepcopy(current)
        next_state.update(
            {
                "phase": "active",
                "last_action": action,
                "last_action_id": str(request.action_id),
                "action_count": int(current.get("action_count", 0)) + 1,
            }
        )
        return _safe_json(next_state)

    def _build_event(
        self,
        room_id: UUID,
        state_version: int,
        game_type: GameType,
        action_id: UUID,
        public_state: dict[str, Any],
    ) -> EventEnvelope:
        return EventEnvelope(
            event_id=action_id,
            room_id=room_id,
            state_version=state_version,
            type=f"{game_type.value}.action.accepted",
            ruleset_version=_RULESET_VERSIONS[game_type],
            server_time=_utc(self.now()),
            payload={"action_id": str(action_id), "public_state": copy.deepcopy(public_state)},
            animation_hint=_ANIMATION_HINTS[game_type],
        )

    async def _load_db_room(self, room_id: UUID, *, lock: bool) -> GameRoom:
        assert self.session is not None
        query = select(GameRoom).where(GameRoom.id == room_id)
        if lock:
            query = query.with_for_update()
        room = (await self.session.execute(query)).scalar_one_or_none()
        if room is None:
            raise RoomNotFoundError("room not found")
        return room

    async def _require_db_member(self, room_id: UUID, user_id: int) -> None:
        assert self.session is not None
        member = (
            await self.session.execute(
                select(GamePlayer).where(GamePlayer.room_id == room_id, GamePlayer.user_id == user_id)
            )
        ).scalar_one_or_none()
        if member is None:
            raise RoomAccessError("user is not a room member")

    @staticmethod
    def _db_snapshot(room: GameRoom) -> RoomSnapshot:
        return RoomSnapshot(
            room_id=room.id,
            game_type=GameType(room.game_type),
            mode=room.mode,
            status=RoomStatus(room.status),
            ruleset_version=room.ruleset_version,
            state_version=room.state_version,
            public_state=copy.deepcopy(room.state_json or {}),
        )

    def _advance_db(
        self, room: GameRoom, user_id: int, request: ActionRequest, action: str
    ) -> EventEnvelope:
        game_type = GameType(room.game_type)
        next_version = room.state_version + 1
        next_state = self._next_public_state(room.state_json or {}, request, action)
        room.state_version = next_version
        room.status = RoomStatus.ACTIVE.value
        room.state_json = next_state
        event = self._build_event(room.id, next_version, game_type, request.action_id, next_state)
        self.session.add(
            GameAction(
                id=request.action_id,
                room_id=room.id,
                user_id=user_id,
                action_type=action,
                payload_json=self._event_record(event),
                sequence_no=next_version,
            )
        )
        return event

    @staticmethod
    def _event_record(event: EventEnvelope) -> dict[str, Any]:
        return {
            "event_type": event.type,
            "ruleset_version": event.ruleset_version,
            "server_time": event.server_time.isoformat(),
            "payload": _safe_json(event.payload),
            "animation_hint": event.animation_hint,
        }

    @staticmethod
    def _event_from_action(room: GameRoom, action: GameAction) -> EventEnvelope:
        record = action.payload_json
        return EventEnvelope(
            event_id=action.id,
            room_id=room.id,
            state_version=action.sequence_no,
            type=record["event_type"],
            ruleset_version=record["ruleset_version"],
            server_time=datetime.fromisoformat(record["server_time"]),
            payload=record["payload"],
            animation_hint=record["animation_hint"],
        )
