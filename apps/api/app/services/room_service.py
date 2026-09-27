from __future__ import annotations

import asyncio
import copy
import json
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from burmaldoza_contracts.common import GameType, RoomStatus
from burmaldoza_contracts.events import EventEnvelope
from burmaldoza_contracts.rooms import ActionRequest, RoomSnapshot, WebSocketAuthMessage
from burmaldoza_domain.core import (
    InsufficientBalanceError,
    InvalidActionError,
    StateVersionConflictError,
)
from burmaldoza_domain.economy import LedgerReason
from burmaldoza_domain.games.blackjack import (
    BlackjackPhase,
    BlackjackRules,
    BlackjackState,
    Card,
    deal_initial,
    settle_blackjack,
)
from burmaldoza_domain.games.blackjack import (
    apply_action as apply_blackjack_action,
)
from burmaldoza_domain.games.slot import SlotConfig, SlotOutcome, spin
from burmaldoza_domain.games.slot_ruleset import load_skeleton_config
from burmaldoza_domain.rng import RandomSource, SystemRandomSource
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.telegram_auth import TelegramAuthError, verify_telegram_init_data
from app.db.models import GameAction, GamePlayer, GameRoom
from app.dependencies import CurrentUser, _upsert_user
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
    private_state: dict[str, Any] = field(default_factory=dict)
    members: set[int] = field(default_factory=set)
    actions: dict[UUID, EventEnvelope] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class _ActionExecution:
    result: dict[str, Any] | None = None
    public_state: dict[str, Any] = field(default_factory=dict)
    private_state: dict[str, Any] = field(default_factory=dict)
    clear_result: bool = False


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
    GameType.BLACKJACK: ("deal", "hit", "stand", "double"),
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
        "legal_actions": ["deal"] if game_type is GameType.BLACKJACK else list(_LEGAL_ACTIONS[game_type]),
        "action_count": 0,
    }


def _serialize_card(card: Card) -> dict[str, str]:
    return {"rank": card.rank, "suit": card.suit}


def _serialize_blackjack_state(state: BlackjackState) -> dict[str, Any]:
    return {
        "phase": state.phase.value,
        "bet": state.bet,
        "player_cards": [_serialize_card(card) for card in state.player_cards],
        "dealer_cards": [_serialize_card(card) for card in state.dealer_cards],
        "dealer_hole_hidden": state.dealer_hole_hidden,
        "player_total": state.player_total,
        "dealer_total": state.dealer_total,
        "state_version": state.state_version,
        "ruleset_version": state.ruleset_version,
        "deck": [_serialize_card(card) for card in state.deck],
        "player_natural_blackjack": state.player_natural_blackjack,
        "doubled": state.doubled,
    }


def _deserialize_blackjack_state(raw: dict[str, Any]) -> BlackjackState:
    try:
        def cards(items: list[dict[str, str]]) -> tuple[Card, ...]:
            return tuple(Card(rank=item["rank"], suit=item["suit"]) for item in items)

        return BlackjackState(
            phase=BlackjackPhase(raw["phase"]),
            bet=raw["bet"],
            player_cards=cards(raw["player_cards"]),
            dealer_cards=cards(raw["dealer_cards"]),
            dealer_hole_hidden=raw["dealer_hole_hidden"],
            player_total=raw["player_total"],
            dealer_total=raw["dealer_total"],
            state_version=raw["state_version"],
            ruleset_version=raw["ruleset_version"],
            deck=cards(raw["deck"]),
            player_natural_blackjack=raw["player_natural_blackjack"],
            doubled=raw["doubled"],
        )
    except (KeyError, TypeError, ValueError) as error:
        raise RoomServiceError("stored blackjack state is invalid") from error


def _blackjack_public_state(state: BlackjackState, wallet_balance: int) -> dict[str, Any]:
    hidden = state.dealer_hole_hidden and state.phase is BlackjackPhase.PLAYER_TURN
    if hidden:
        dealer_cards: list[dict[str, Any]] = [
            _serialize_card(state.dealer_cards[0]),
            {"hidden": True},
        ]
    else:
        dealer_cards = [_serialize_card(card) for card in state.dealer_cards]
    if state.phase is BlackjackPhase.PLAYER_TURN:
        legal_actions = ["hit", "stand"]
        if len(state.player_cards) == 2:
            legal_actions.append("double")
    else:
        legal_actions = ["deal"]
    public: dict[str, Any] = {
        "game_phase": state.phase.value,
        "bet": state.bet,
        "player_cards": [_serialize_card(card) for card in state.player_cards],
        "dealer_cards": dealer_cards,
        "dealer_hole_hidden": hidden,
        "player_total": state.player_total,
        "legal_actions": legal_actions,
        "ruleset_version": state.ruleset_version,
        "wallet_balance": wallet_balance,
    }
    if not hidden:
        public["dealer_total"] = state.dealer_total
    return public


def _action_ledger_key(action_id: UUID, purpose: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"burmaldoza:room-action:{action_id}:{purpose}")


def _action_name(request: ActionRequest, game_type: GameType) -> str:
    raw_action = request.payload.get("action", request.payload.get("type"))
    if not isinstance(raw_action, str):
        raise RoomServiceError("action payload must include a string action")
    action = raw_action.lower().strip()
    if action not in _LEGAL_ACTIONS[game_type]:
        raise RoomServiceError(f"action {action!r} is not legal for {game_type.value}")
    if game_type is GameType.BLACKJACK:
        if action == "deal":
            bet = request.payload.get("bet")
            if isinstance(bet, bool) or not isinstance(bet, int) or not 25 <= bet <= 100:
                raise RoomServiceError("blackjack bet must be an integer between 25 and 100")
        elif "bet" in request.payload:
            raise RoomServiceError("blackjack bet is only accepted with deal")
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
        blackjack_rng: RandomSource | None = None,
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
        self.blackjack_rng = blackjack_rng or SystemRandomSource()
        self.blackjack_rules = BlackjackRules()
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

        return await _upsert_user(self.session, context)

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
        execution = await self._execute_game_action(
            room.room_id,
            user_id,
            request,
            room.game_type,
            action,
            room.private_state,
        )
        room.state_version += 1
        room.status = RoomStatus.ACTIVE
        room.public_state = self._next_public_state(
            room.public_state,
            request,
            action,
            execution.result,
            execution.public_state,
            execution.clear_result,
        )
        room.private_state = execution.private_state
        event = self._build_event(
            room.room_id,
            room.state_version,
            room.game_type,
            request.action_id,
            room.public_state,
            execution.result,
        )
        room.actions[request.action_id] = event
        return event

    def _next_public_state(
        self,
        current: dict[str, Any],
        request: ActionRequest,
        action: str,
        result: dict[str, Any] | None = None,
        game_state: dict[str, Any] | None = None,
        clear_result: bool = False,
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
        if clear_result:
            next_state.pop("last_result", None)
        if game_state:
            next_state.update(copy.deepcopy(game_state))
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
        private_state: dict[str, Any],
    ) -> _ActionExecution:
        if game_type is GameType.SLOT:
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

            return _ActionExecution(
                result=_serialize_slot_result(outcome, settlement),
                private_state=private_state,
            )

        if game_type is GameType.BLACKJACK:
            return await self._execute_blackjack_action(
                room_id, user_id, request, action, private_state
            )

        return _ActionExecution(private_state=private_state)

    async def _execute_blackjack_action(
        self,
        room_id: UUID,
        user_id: int,
        request: ActionRequest,
        action: str,
        private_state: dict[str, Any],
    ) -> _ActionExecution:
        stored_round = private_state.get("blackjack_round")
        if action == "deal":
            if stored_round is not None:
                previous_state = _deserialize_blackjack_state(stored_round["state"])
                if previous_state.phase is BlackjackPhase.PLAYER_TURN:
                    raise RoomServiceError("blackjack hand is still in progress")
            bet = request.payload["bet"]
            round_id = uuid5(NAMESPACE_URL, f"blackjack:{room_id}:{request.action_id}")
            try:
                state = deal_initial(bet, self.blackjack_rng, self.blackjack_rules)
            except ValueError as error:
                raise RoomServiceError(str(error)) from error
            state = replace(state, state_version=request.expected_state_version + 1)
            try:
                stake = await self.wallet_service.apply_delta_in_transaction(
                    user_id=user_id,
                    delta=-bet,
                    reason=LedgerReason.GAME_STAKE,
                    reference_id=round_id,
                    idempotency_key=_action_ledger_key(request.action_id, "stake"),
                )
            except InsufficientBalanceError as error:
                raise RoomServiceError("insufficient balance for blackjack bet") from error
            payout = (
                await self._settle_blackjack_action(
                    user_id, request.action_id, round_id, state
                )
                if state.phase is not BlackjackPhase.PLAYER_TURN
                else None
            )
            wallet_balance = payout["balance_after"] if payout is not None else stake.balance_after
            next_private_state = {
                "blackjack_round": {
                    "round_id": str(round_id),
                    "state": _serialize_blackjack_state(state),
                }
            }
            return _ActionExecution(
                result=payout,
                public_state=_blackjack_public_state(state, wallet_balance),
                private_state=next_private_state,
                clear_result=True,
            )

        if stored_round is None:
            raise RoomServiceError("blackjack must be dealt before a player action")
        round_id = UUID(stored_round["round_id"])
        state = _deserialize_blackjack_state(stored_round["state"])
        try:
            transition = apply_blackjack_action(
                state,
                action,  # type: ignore[arg-type]
                self.blackjack_rng,
                self.blackjack_rules,
            )
        except InvalidActionError as error:
            raise RoomServiceError(str(error)) from error

        added_stake = transition.state.bet - state.bet
        if added_stake > 0:
            try:
                await self.wallet_service.apply_delta_in_transaction(
                    user_id=user_id,
                    delta=-added_stake,
                    reason=LedgerReason.GAME_STAKE,
                    reference_id=round_id,
                    idempotency_key=_action_ledger_key(request.action_id, "stake"),
                )
            except InsufficientBalanceError as error:
                raise RoomServiceError("insufficient balance for blackjack double") from error

        result = None
        if transition.settlement is not None:
            result = await self._settle_blackjack_action(
                user_id,
                request.action_id,
                round_id,
                transition.state,
                outcome=transition.settlement.result,
            )
        wallet = await self.wallet_service.get_or_create_in_transaction(user_id)
        next_private_state = {
            "blackjack_round": {
                "round_id": str(round_id),
                "state": _serialize_blackjack_state(transition.state),
            }
        }
        return _ActionExecution(
            result=result,
            public_state=_blackjack_public_state(transition.state, wallet.balance),
            private_state=next_private_state,
        )

    async def _settle_blackjack_action(
        self,
        user_id: int,
        action_id: UUID,
        round_id: UUID,
        state: BlackjackState,
        *,
        outcome: str | None = None,
    ) -> dict[str, Any]:
        settlement = settle_blackjack(state, self.blackjack_rules)
        if settlement.payout > 0:
            await self.wallet_service.apply_delta_in_transaction(
                user_id=user_id,
                delta=settlement.payout,
                reason=LedgerReason.GAME_PAYOUT,
                reference_id=round_id,
                idempotency_key=_action_ledger_key(action_id, "payout"),
            )
        wallet = await self.wallet_service.get_or_create_in_transaction(user_id)
        return {
            "outcome": outcome or settlement.result,
            "player_total": settlement.player_total,
            "dealer_total": settlement.dealer_total,
            "gross_payout": settlement.payout,
            "net_delta": settlement.payout - state.bet,
            "balance_after": wallet.balance,
            "ruleset_version": settlement.ruleset_version,
            "final_bet": state.bet,
        }

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
        execution = await self._execute_game_action(
            room.id,
            user_id,
            request,
            game_type,
            action,
            room.private_state_json or {},
        )
        next_state = self._next_public_state(
            room.state_json or {},
            request,
            action,
            execution.result,
            execution.public_state,
            execution.clear_result,
        )
        room.state_version = next_version
        room.status = RoomStatus.ACTIVE.value
        room.state_json = next_state
        room.private_state_json = execution.private_state
        event = self._build_event(
            room.id, next_version, game_type, request.action_id, next_state, execution.result
        )
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
