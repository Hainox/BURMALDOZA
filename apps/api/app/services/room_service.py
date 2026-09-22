from __future__ import annotations

import asyncio
import copy
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from burmaldoza_contracts.common import GameType, RoomStatus
from burmaldoza_contracts.events import EventEnvelope
from burmaldoza_contracts.rooms import ActionRequest, RoomSnapshot, WebSocketAuthMessage
from burmaldoza_domain.core import InsufficientBalanceError, StateVersionConflictError
from burmaldoza_domain.games.slot import SlotConfig, SlotOutcome, spin
from burmaldoza_domain.games.slot_ruleset import load_skeleton_config
from burmaldoza_domain.rng import RandomSource, SystemRandomSource
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.telegram_auth import TelegramAuthError, verify_telegram_init_data
from app.db.models import GameAction, GamePlayer, GameRoom, User
from app.dependencies import CurrentUser
from app.services.event_bus import EventBus
from app.services.wallet_service import MemoryWalletStore, SettlementResult, WalletService


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


def _serialize_slot_result(outcome: SlotOutcome, settlement: SettlementResult) -> dict[str, Any]:
    return {
        "grid": [list(column) for column in outcome.grid],
        "reel_stops": list(outcome.reel_stops),
        "winning_lines": [
            {
                "payline_index": line.payline_index,
                "rows": list(line.rows),
                "symbols": list(line.symbols),
                "match_symbol": line.match_symbol,
                "matched_columns": line.matched_columns,
                "payout": line.payout,
            }
            for line in outcome.winning_lines
        ],
        "gross_payout": outcome.gross_payout,
        "net_delta": settlement.net_delta,
        "balance_after": settlement.balance_after,
        "ruleset_version": outcome.ruleset_version,
    }


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
        wallet_service: WalletService | None = None,
        slot_config: SlotConfig | None = None,
        slot_rng: RandomSource | None = None,
        bot_token: str = "",
        max_auth_age_seconds: int = 86400,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if session is not None and store is not None:
            raise ValueError("provide either session or store")
        self.session = session
        self.store = store if store is not None else (None if session is not None else MemoryRoomStore())
        self.event_bus = event_bus or EventBus()
        self.wallet_service = wallet_service or (
            WalletService(session=session)
            if session is not None
            else WalletService(store=MemoryWalletStore())
        )
        self.slot_config = slot_config or load_skeleton_config()
        self.slot_rng = slot_rng or SystemRandomSource()
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
                replay = self._find_memory_action(room_id, request.action_id)
                if replay is not None:
                    return replay
                if request.expected_state_version != room.state_version:
                    raise StateVersionConflictError(
                        f"expected state_version {request.expected_state_version}, current is {room.state_version}"
                    )
                action = _action_name(request, room.game_type)
                event = await self._advance_memory(room, user_id, request, action)
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
                event = await self._advance_db(room, user_id, request, action)
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

    def _find_memory_action(self, room_id: UUID, action_id: UUID) -> EventEnvelope | None:
        assert self.store is not None
        for stored_room in self.store.rooms.values():
            replay = stored_room.actions.get(action_id)
            if replay is None:
                continue
            if stored_room.room_id != room_id:
                raise RoomServiceError("action_id already belongs to another room")
            return replay
        return None

    @staticmethod
    def _require_member(room: _MemoryRoom, user_id: int) -> None:
        if user_id not in room.members:
            raise RoomAccessError("user is not a room member")

    async def _advance_memory(
        self, room: _MemoryRoom, user_id: int, request: ActionRequest, action: str
    ) -> EventEnvelope:
        result = await self._execute_game_action(room.room_id, user_id, request, room.game_type, action)
        room.state_version += 1
        room.status = RoomStatus.ACTIVE
        room.public_state = self._next_public_state(room.public_state, request, action, result)
        event = self._build_event(
            room.room_id,
            room.state_version,
            room.game_type,
            request.action_id,
            room.public_state,
            result,
        )
        room.actions[request.action_id] = event
        return event

    def _next_public_state(
        self,
        current: dict[str, Any],
        request: ActionRequest,
        action: str,
        result: dict[str, Any] | None = None,
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
        if result is not None:
            next_state["last_result"] = copy.deepcopy(result)
        return _safe_json(next_state)

    def _build_event(
        self,
        room_id: UUID,
        state_version: int,
        game_type: GameType,
        action_id: UUID,
        public_state: dict[str, Any],
        result: dict[str, Any] | None = None,
    ) -> EventEnvelope:
        payload: dict[str, Any] = {
            "action_id": str(action_id),
            "public_state": copy.deepcopy(public_state),
        }
        if result is not None:
            payload["result"] = copy.deepcopy(result)
        return EventEnvelope(
            event_id=action_id,
            room_id=room_id,
            state_version=state_version,
            type=f"{game_type.value}.action.accepted",
            ruleset_version=_RULESET_VERSIONS[game_type],
            server_time=_utc(self.now()),
            payload=payload,
            animation_hint=_ANIMATION_HINTS[game_type],
        )

    async def _execute_game_action(
        self,
        room_id: UUID,
        user_id: int,
        request: ActionRequest,
        game_type: GameType,
        action: str,
    ) -> dict[str, Any] | None:
        if game_type is not GameType.SLOT:
            return None
        if action != "spin":
            raise RoomServiceError(f"action {action!r} is not supported by the slot room")

        bet = request.payload.get("bet", 10)
        if isinstance(bet, bool) or not isinstance(bet, int) or not 10 <= bet <= 100:
            raise RoomServiceError("slot bet must be an integer between 10 and 100")

        raw_paylines = request.payload.get("paylines", tuple(range(len(self.slot_config.paylines))))
        if not isinstance(raw_paylines, (list, tuple)) or any(
            isinstance(index, bool) or not isinstance(index, int) for index in raw_paylines
        ):
            raise RoomServiceError("slot paylines must be a list of integer indexes")
        active_paylines = tuple(raw_paylines)

        try:
            outcome = spin(self.slot_config, bet, active_paylines, self.slot_rng)
        except ValueError as error:
            raise RoomServiceError(str(error)) from error

        round_id = uuid5(NAMESPACE_URL, f"slot:{room_id}:{request.action_id}")
        try:
            settlement = await self.wallet_service.settle_game_round_in_transaction(
                user_id=user_id,
                round_id=round_id,
                stake=bet,
                payout=outcome.gross_payout,
                idempotency_key=request.action_id,
            )
        except InsufficientBalanceError as error:
            raise RoomServiceError("insufficient balance for slot bet") from error

        return _serialize_slot_result(outcome, settlement)

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

    async def _advance_db(
        self, room: GameRoom, user_id: int, request: ActionRequest, action: str
    ) -> EventEnvelope:
        game_type = GameType(room.game_type)
        next_version = room.state_version + 1
        result = await self._execute_game_action(room.id, user_id, request, game_type, action)
        next_state = self._next_public_state(room.state_json or {}, request, action, result)
        room.state_version = next_version
        room.status = RoomStatus.ACTIVE.value
        room.state_json = next_state
        event = self._build_event(room.id, next_version, game_type, request.action_id, next_state, result)
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
