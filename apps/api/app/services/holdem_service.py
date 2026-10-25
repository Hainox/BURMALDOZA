"""Durable heads-up games. Only seat-specific outbound projections contain hole cards."""

from __future__ import annotations

import asyncio
import copy
import json
import logging
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from typing import TYPE_CHECKING, Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from burmaldoza_contracts.events import EventEnvelope
from burmaldoza_contracts.rooms import ActionRequest, HoldemOpponentProfile, RoomSnapshot
from burmaldoza_domain.core import (
    InvalidActionError,
    StateVersionConflictError,
)
from burmaldoza_domain.economy import LedgerReason
from burmaldoza_domain.games.blackjack import Card
from burmaldoza_domain.games.holdem import (
    HoldemAction,
    HoldemPhase,
    HoldemPlayerState,
    HoldemState,
    apply_holdem_action,
    create_heads_up_room,
    settle_holdem,
)
from burmaldoza_domain.games.holdem_bot import (
    BotObservation,
    choose_bot_action,
    legal_holdem_actions,
    rules_for_buy_in,
)
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import GameAction, GamePlayer, GameRoom, GameRound, HoldemHeroBag
from app.services.wallet_service import LedgerResult, WalletServiceError

if TYPE_CHECKING:
    from app.services.room_service import RoomService

# One process is a deployment invariant. PostgreSQL locks additionally protect transactions.
_QUEUE_LOCK = asyncio.Lock()
_HERO_POOLS = json.loads(
    files("burmaldoza_domain.games").joinpath("holdem_hero_pools.json").read_text()
)


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def encode_state(state: HoldemState) -> dict[str, Any]:
    raw = asdict(state)
    raw["phase"] = state.phase.value
    return json.loads(json.dumps(raw))


def decode_state(raw: dict[str, Any]) -> HoldemState:
    fields = dict(raw)
    fields["phase"] = HoldemPhase(raw["phase"])
    fields["players"] = tuple(HoldemPlayerState(**item) for item in raw["players"])
    fields["hole_cards"] = tuple(tuple(Card(**item) for item in hand) for hand in raw["hole_cards"])
    for name in ("community_cards", "deck"):
        fields[name] = tuple(Card(**item) for item in raw[name])
    for name in ("contributions", "street_contributions", "acted_seats"):
        fields[name] = tuple(raw[name])
    return HoldemState(**fields)


class HoldemService:
    def __init__(self, rooms: RoomService) -> None:
        self.rooms = rooms
        self.session = rooms.session
        self.wallet = rooms.wallet_service
        self.rng = rooms.holdem_rng

    def require_database(self) -> None:
        from app.services.room_service import RoomServiceError

        if self.session is None:
            raise RoomServiceError("Hold'em requires durable database storage")

    async def queue_lock(self) -> None:
        if self.session.get_bind().dialect.name == "postgresql":
            await self.session.execute(text("SELECT pg_advisory_xact_lock(530001)"))

    async def create(
        self, user_id: int, mode: str, buy_in: int | None, action_id: UUID | None
    ) -> RoomSnapshot:
        from app.services.room_service import RoomServiceError

        if (
            mode not in ("bot", "pvp")
            or type(buy_in) is not int
            or buy_in not in (100, 500, 1000)
            or not isinstance(action_id, UUID)
        ):
            raise RoomServiceError(
                "Hold'em requires mode bot/pvp, buy_in 100/500/1000 and action_id"
            )
        self.require_database()
        event = None
        cancelled_events = []
        async with _QUEUE_LOCK, self.session.begin():
            await self.queue_lock()
            replay = await self.session.get(GameAction, action_id)
            if replay is not None:
                metadata = replay.payload_json.get("creation")
                if replay.user_id != user_id or metadata != {"mode": mode, "buy_in": buy_in}:
                    raise RoomServiceError("action_id belongs to a different action")
                room = await self.rooms._load_db_room(replay.room_id, lock=True)
                return await self.project_snapshot(room, user_id)
            waiting = list(
                (
                    await self.session.scalars(
                        select(GameRoom)
                        .join(GamePlayer)
                        .where(
                            GameRoom.game_type == "holdem",
                            GameRoom.mode == "pvp",
                            GameRoom.status.in_(["waiting", "active"]),
                            GamePlayer.user_id == user_id,
                        )
                        .with_for_update()
                    )
                ).all()
            )
            if mode == "pvp" and any(
                room.status == "active" or room.ruleset_version == "holdem-six-1"
                or (room.deadline_at and utc(room.deadline_at) > utc(self.rooms.now()))
                for room in waiting
            ):
                raise RoomServiceError("player is already searching for an opponent")
            candidates = (
                list(
                    (
                        await self.session.scalars(
                            select(GameRoom)
                            .where(
                                GameRoom.game_type == "holdem",
                                GameRoom.mode == "pvp",
                                GameRoom.status == "waiting",
                                GameRoom.ruleset_version == "holdem-v1",
                                GameRoom.deadline_at > utc(self.rooms.now()),
                                GameRoom.state_json["buy_in"].as_integer() == buy_in,
                            )
                            .order_by(GameRoom.created_at, GameRoom.id)
                            .limit(100)
                            .with_for_update()
                        )
                    ).all()
                )
                if mode == "pvp"
                else []
            )
            owners = (
                dict(
                    (
                        await self.session.execute(
                            select(GamePlayer.room_id, GamePlayer.user_id).where(
                                GamePlayer.room_id.in_([candidate.id for candidate in candidates]),
                                GamePlayer.seat == 0,
                            )
                        )
                    ).all()
                )
                if candidates
                else {}
            )
            # Acquire the entire bounded batch in one global order. Locking the caller
            # first, or a new candidate after the previous pair, can invert wallet locks.
            balances = {}
            for member_id in sorted({user_id, *owners.values()}):
                balances[member_id] = (
                    await self.wallet.get_or_create_in_transaction(member_id)
                ).balance
            if balances[user_id] < buy_in:
                raise RoomServiceError("insufficient balance for Hold'em buy-in")
            selected = None
            for candidate in candidates:
                owner_id = owners[candidate.id]
                if owner_id == user_id:
                    raise RoomServiceError("player cannot match themselves")
                if balances[owner_id] < buy_in:
                    candidate.status = "closed"
                    candidate.deadline_at = None
                    candidate.state_json = {
                        **candidate.state_json,
                        "phase": "cancelled",
                        "search_deadline": None,
                        "cancel_reason": "insufficient_balance",
                    }
                    cancelled_events.append(
                        await self.record(
                            candidate,
                            owner_id,
                            uuid5(candidate.id, f"queue-balance:{candidate.state_version}"),
                            "search_balance_unavailable",
                        )
                    )
                    continue
                selected = candidate
                break
            if selected is not None:
                room = selected
                self.session.add(GamePlayer(room_id=room.id, user_id=user_id, seat=1, stack=buy_in))
                await self.session.flush()
                await self.start(room, action_id)
            else:
                room = GameRoom(
                    id=uuid4(),
                    game_type="holdem",
                    mode=mode,
                    status="waiting",
                    ruleset_version="holdem-v1",
                    state_version=0,
                    state_json={"phase": "waiting", "buy_in": buy_in, "legal_actions": []},
                    private_state_json={},
                    deadline_at=utc(self.rooms.now()) + timedelta(seconds=60)
                    if mode == "pvp"
                    else None,
                )
                self.session.add(room)
                await self.session.flush()
                self.session.add(GamePlayer(room_id=room.id, user_id=user_id, seat=0, stack=buy_in))
                await self.session.flush()
                if mode == "bot":
                    await self.start(room, action_id)
                else:
                    room.state_json = {
                        **room.state_json,
                        "search_deadline": room.deadline_at.isoformat(),
                    }
            event = await self.record(
                room, user_id, action_id, "create", creation={"mode": mode, "buy_in": buy_in}
            )
            snapshot = await self.project_snapshot(room, user_id)
        for cancelled_event in cancelled_events:
            await self.rooms.event_bus.publish(cancelled_event)
        await self.rooms.event_bus.publish(event)
        return snapshot

    async def members(self, room_id: UUID) -> dict[int, int]:
        players = (
            await self.session.scalars(
                select(GamePlayer).where(GamePlayer.room_id == room_id).order_by(GamePlayer.seat)
            )
        ).all()
        return {player.seat: player.user_id for player in players}

    async def hero(self, user_id: int, buy_in: int) -> str:
        # create() holds the durable queue lock, including for bot games.
        bag = await self.session.get(HoldemHeroBag, (user_id, buy_in), with_for_update=True)
        if bag is None:
            bag = HoldemHeroBag(user_id=user_id, buy_in=buy_in, remaining_json=[])
            self.session.add(bag)
        remaining = list(bag.remaining_json)
        if not remaining:
            remaining = list(_HERO_POOLS[str(buy_in)])
            self.rng.shuffle(remaining)
        chosen = remaining.pop()
        bag.remaining_json = remaining
        return chosen

    async def lock_wallets(self, members: dict[int, int], buy_in: int | None = None) -> None:
        from app.services.room_service import RoomServiceError

        for user_id in sorted(members.values()):
            wallet = await self.wallet.get_or_create_in_transaction(user_id)
            if buy_in is not None and wallet.balance < buy_in:
                raise RoomServiceError("insufficient balance for Hold'em buy-in")

    async def apply_game_delta(
        self,
        *,
        user_id: int,
        delta: int,
        reason: LedgerReason,
        reference_id: UUID,
        idempotency_key: UUID,
    ) -> LedgerResult:
        from app.services.room_service import RoomServiceError

        try:
            result = await self.wallet.apply_delta_in_transaction(
                user_id=user_id,
                delta=delta,
                reason=reason,
                reference_id=reference_id,
                idempotency_key=idempotency_key,
            )
        except WalletServiceError as error:
            raise RoomServiceError("Hold'em ledger operation conflict") from error
        # WalletService replay may return a grant recorded under the same UUID.
        # A mismatched operation must roll back the whole game transaction.
        if (result.user_id, result.delta, result.reason, result.reference_id) != (
            user_id,
            delta,
            reason,
            reference_id,
        ):
            raise RoomServiceError("Hold'em ledger operation conflict")
        return result

    async def start(self, room: GameRoom, action_id: UUID) -> None:
        buy_in = room.state_json["buy_in"]
        members = await self.members(room.id)
        await self.lock_wallets(members, buy_in)
        entry_balances = {}
        for user_id in sorted(members.values()):
            stake = await self.apply_game_delta(
                user_id=user_id,
                delta=-buy_in,
                reason=LedgerReason.GAME_STAKE,
                reference_id=room.id,
                idempotency_key=uuid5(NAMESPACE_URL, f"holdem:{action_id}:stake:{user_id}"),
            )
            seat = next(seat for seat, member in members.items() if member == user_id)
            entry_balances[str(seat)] = stake.balance_after
        state = create_heads_up_room(buy_in, self.rng, rules_for_buy_in(buy_in))
        hero = await self.hero(members[0], buy_in) if room.mode == "bot" else None
        room.private_state_json = {
            "state": encode_state(state),
            "hero_code": hero,
            "entry_balances": entry_balances,
        }
        room.status = "active"
        self.session.add(
            GameRound(
                id=room.id,
                room_id=room.id,
                round_no=1,
                bet_amount=buy_in * len(members),
                payout_amount=0,
                status="active",
                idempotency_key=uuid5(action_id, "holdem-round"),
                outcome_json={"buy_in": buy_in, "mode": room.mode, "hero_code": hero},
            )
        )
        await self.session.flush()
        await self.update(room, state, action_id)

    async def update(self, room: GameRoom, state: HoldemState, action_id: UUID) -> None:
        buy_in = room.state_json["buy_in"]
        members = await self.members(room.id)
        rules = rules_for_buy_in(buy_in)
        # A bot may act again on each new street; bound the loop independently of policy.
        for _ in range(20):
            if (
                room.mode != "bot"
                or state.current_seat != 1
                or state.phase in (HoldemPhase.SHOWDOWN, HoldemPhase.SETTLED)
            ):
                break
            action = choose_bot_action(
                BotObservation(
                    hole_cards=state.hole_cards[1],
                    community_cards=state.community_cards,
                    legal_actions=legal_holdem_actions(state, 1, rules),
                    amount_to_call=state.current_bet - state.street_contributions[1],
                    stack=state.players[1].stack,
                    street_contribution=state.street_contributions[1],
                    current_bet=state.current_bet,
                    big_blind=rules.big_blind,
                    buy_in=buy_in,
                ),
                self.rng,
            )
            state = apply_holdem_action(state, 1, action, self.rng, rules).state
        else:
            raise RuntimeError("Hold'em bot exceeded bounded decision loop")
        finished = state.phase in (HoldemPhase.SHOWDOWN, HoldemPhase.SETTLED)
        public = {
            "phase": "settled" if finished else "active",
            "game_phase": state.phase.value,
            "buy_in": buy_in,
            "hero_code": room.private_state_json.get("hero_code"),
            "community_cards": [asdict(card) for card in state.community_cards],
            "pot": state.pot,
            "current_bet": state.current_bet,
            "current_seat": state.current_seat,
            "stacks": list(state.stacks),
            "street_contributions": list(state.street_contributions),
            "small_blind": rules.small_blind,
            "big_blind": rules.big_blind,
            "minimum_raise": state.current_bet + rules.big_blind,
            "legal_actions_by_seat": [
                list(legal_holdem_actions(state, seat, rules)) for seat in (0, 1)
            ],
            "showdown": finished and state.folded_seat is None,
        }
        if finished:
            settlement = settle_holdem(state)
            await self.lock_wallets(members)
            payouts = [state.players[seat].stack + settlement.shares[seat] for seat in (0, 1)]
            balances = {}
            for seat, user_id in sorted(members.items(), key=lambda item: item[1]):
                if payouts[seat]:
                    await self.apply_game_delta(
                        user_id=user_id,
                        delta=payouts[seat],
                        reason=LedgerReason.GAME_PAYOUT,
                        reference_id=room.id,
                        idempotency_key=uuid5(
                            NAMESPACE_URL, f"holdem:{action_id}:payout:{user_id}"
                        ),
                    )
                balances[str(seat)] = (
                    await self.wallet.get_or_create_in_transaction(user_id)
                ).balance
            public["last_result"] = {
                "winner_seats": list(settlement.winner_seats),
                "payouts": payouts,
                "net_deltas": [payout - buy_in for payout in payouts],
                "outcome": "fold" if state.folded_seat is not None else "showdown",
                "hero_code": public["hero_code"],
            }
            # Balances are seat-private just like cards; never enter the shared bus.
            room.private_state_json = {**room.private_state_json, "balances": balances}
            room.status = "settled"
            history = await self.session.get(GameRound, room.id)
            history.status = "settled"
            history.payout_amount = sum(payouts[seat] for seat in members)
            history.outcome_json = {**history.outcome_json, **public["last_result"]}

        room.deadline_at = (
            utc(self.rooms.now()) + timedelta(seconds=20)
            if room.mode == "pvp" and not finished
            else None
        )
        public["turn_deadline"] = room.deadline_at.isoformat() if room.deadline_at else None
        room.state_json = public
        room.private_state_json = {**room.private_state_json, "state": encode_state(state)}

    async def record(
        self,
        room: GameRoom,
        user_id: int,
        action_id: UUID,
        action: str,
        *,
        creation: dict | None = None,
        request_payload: dict | None = None,
    ) -> EventEnvelope:
        room.state_version += 1
        event = EventEnvelope(
            event_id=action_id,
            room_id=room.id,
            state_version=room.state_version,
            type="holdem.action.accepted",
            ruleset_version="holdem-v1",
            server_time=utc(self.rooms.now()),
            payload={"action_id": str(action_id), "public_state": copy.deepcopy(room.state_json)},
            animation_hint="holdem.action.confirmed",
        )
        record = self.rooms._event_record(event)
        if creation is not None:
            record["creation"] = creation
        if request_payload is not None:
            record["request_payload"] = copy.deepcopy(request_payload)
        self.session.add(
            GameAction(
                id=action_id,
                room_id=room.id,
                user_id=user_id,
                action_type=action,
                payload_json=record,
                sequence_no=room.state_version,
            )
        )
        await self.session.flush()
        return event

    async def apply(self, room_id: UUID, user_id: int, request: ActionRequest) -> EventEnvelope:
        from app.services.room_service import RoomServiceError

        self.require_database()
        # Single-process serialization also makes SQLite unit runs meaningful. PG room row locks
        # remain the production guard; transaction acquires wallets in sorted order.
        async with _QUEUE_LOCK, self.session.begin():
            room = await self.rooms._load_db_room(room_id, lock=True)
            await self.rooms._require_db_member(room_id, user_id)
            replay = await self.session.get(GameAction, request.action_id)
            if replay is not None:
                if (
                    replay.room_id != room_id
                    or replay.user_id != user_id
                    or replay.payload_json.get("request_payload") != request.payload
                ):
                    raise RoomServiceError("action_id belongs to a different action")
                event = self.rooms._event_from_action(room, replay)
                return await self.project_event(room, event, user_id)
            if room.state_version != request.expected_state_version:
                raise StateVersionConflictError("Hold'em action uses an old state version")
            if request.payload == {"action": "cancel"}:
                if room.status != "waiting" or room.mode != "pvp":
                    raise RoomServiceError("only a waiting Hold'em search can be cancelled")
                room.status = "closed"
                room.deadline_at = None
                room.state_json = {
                    **room.state_json,
                    "phase": "cancelled",
                    "search_deadline": None,
                    "cancel_reason": "player_cancelled",
                }
                event = await self.record(
                    room, user_id, request.action_id, "cancel", request_payload=request.payload
                )
                projected = await self.project_event(room, event, user_id)
            else:
                event, projected = await self.apply_move(room, user_id, request)
        await self.rooms.event_bus.publish(event)
        return projected

    async def apply_move(
        self, room: GameRoom, user_id: int, request: ActionRequest
    ) -> tuple[EventEnvelope, EventEnvelope]:
        from app.services.room_service import RoomServiceError

        if room.status != "active":
            raise RoomServiceError("Hold'em hand is not active")
        if room.deadline_at and utc(room.deadline_at) <= utc(self.rooms.now()):
            raise RoomServiceError("Hold'em turn deadline has expired")
        action = self.validate_action(request.payload)
        members = await self.members(room.id)
        seat = next(seat for seat, member in members.items() if member == user_id)
        state = decode_state(room.private_state_json["state"])
        try:
            transition = apply_holdem_action(
                state, seat, action, self.rng, rules_for_buy_in(room.state_json["buy_in"])
            )
        except (InvalidActionError, ValueError) as error:
            raise RoomServiceError(str(error)) from error
        await self.update(room, transition.state, request.action_id)
        event = await self.record(
            room, user_id, request.action_id, action.kind.value, request_payload=request.payload
        )
        projected = await self.project_event(room, event, user_id)
        return event, projected

    @staticmethod
    def validate_action(payload: dict[str, Any]) -> HoldemAction:
        from app.services.room_service import RoomServiceError

        if set(payload) - {"action", "amount"} or payload.get("action") not in (
            "fold",
            "check",
            "call",
            "raise",
        ):
            raise RoomServiceError("invalid Hold'em action payload")
        amount = payload.get("amount")
        if amount is not None and (type(amount) is not int or amount < 0):
            raise RoomServiceError("Hold'em amount must be a non-negative integer")
        if payload["action"] == "raise" and amount is None:
            raise RoomServiceError("raise amount is required")
        if payload["action"] in ("check", "fold") and amount is not None:
            raise RoomServiceError("amount is not accepted for check/fold")
        return HoldemAction(payload["action"], amount)

    async def project_public(
        self, room: GameRoom, public: dict[str, Any], user_id: int
    ) -> dict[str, Any]:
        from app.services.room_service import RoomAccessError

        members = await self.members(room.id)
        seat = next((seat for seat, member in members.items() if member == user_id), None)
        if seat is None:
            raise RoomAccessError("user is not a room member")
        result = copy.deepcopy(public)
        result["opponent_profile"] = None
        if room.mode == "pvp" and len(members) == 2 and public.get("phase") in ("active", "settled"):
            from app.db.models import User

            opponent = await self.session.get(User, members[1 - seat])
            result["opponent_profile"] = HoldemOpponentProfile(
                nickname=f"@{opponent.username}" if opponent.username else "Живой игрок",
                avatar_path=f"/api/v1/rooms/{room.id}/opponent-avatar",
            ).model_dump()
        result["seat"] = seat
        result["legal_actions"] = result.pop("legal_actions_by_seat", [[], []])[seat]
        if room.private_state_json.get("state") and public.get("phase") in ("active", "settled"):
            # A room is one immutable hand. Project cards against event-at-version flags,
            # never against latest phase: queued pre-showdown events stay private.
            state = room.private_state_json["state"]
            result["hole_cards"] = copy.deepcopy(state["hole_cards"][seat])
            result["opponent_cards"] = (
                copy.deepcopy(state["hole_cards"][1 - seat])
                if result.get("showdown")
                else [{"hidden": True}, {"hidden": True}]
            )
            balances = room.private_state_json.get(
                "balances" if result.get("phase") == "settled" else "entry_balances", {}
            )
            result["wallet_balance"] = balances.get(str(seat))
            if result.get("last_result"):
                result["last_result"]["balance_after"] = room.private_state_json.get(
                    "balances", {}
                ).get(str(seat))
        return result

    async def project_snapshot(self, room: GameRoom, user_id: int) -> RoomSnapshot:
        snapshot = self.rooms._db_snapshot(room)
        public = await self.project_public(room, room.state_json, user_id)
        public["wallet_balance"] = (await self.wallet.get_or_create_in_transaction(user_id)).balance
        return snapshot.model_copy(update={"public_state": public})

    async def project_event(
        self, room: GameRoom, event: EventEnvelope, user_id: int
    ) -> EventEnvelope:
        payload = copy.deepcopy(event.payload)
        payload["public_state"] = await self.project_public(room, payload["public_state"], user_id)
        if payload["public_state"].get("last_result"):
            payload["result"] = copy.deepcopy(payload["public_state"]["last_result"])
        return event.model_copy(update={"payload": payload})

    async def history(self, user_id: int, limit: int, offset: int) -> list[dict[str, Any]]:
        self.require_database()
        async with self.session.begin():
            rows = (
                await self.session.execute(
                    select(GameRound, GamePlayer.seat, GameRoom.ruleset_version)
                    .join(GamePlayer, GamePlayer.room_id == GameRound.room_id)
                    .join(GameRoom, GameRoom.id == GameRound.room_id)
                    .where(GameRoom.game_type == "holdem", GamePlayer.user_id == user_id)
                    .order_by(GameRound.created_at.desc(), GameRound.id.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
            history = []
            for hand, seat, version in rows:
                outcome = hand.outcome_json
                if version == "holdem-six-1":
                    payout = outcome.get("cashouts", {}).get(str(seat))
                    net = outcome.get("net_deltas", {}).get(str(seat))
                elif version == "holdem-v1":
                    payout = outcome.get("payouts", [None, None])[seat]
                    net = outcome.get("net_deltas", [None, None])[seat]
                else:
                    from app.services.room_service import RoomServiceError
                    raise RoomServiceError("unknown ruleset in history")
                history.append(
                    {
                        "room_id": str(hand.room_id),
                        "status": hand.status,
                        "created_at": utc(hand.created_at).isoformat(),
                        "buy_in": outcome["buy_in"],
                        "mode": outcome["mode"],
                        "hero_code": outcome["hero_code"],
                        "seat": seat,
                        "payout": payout,
                        "net_delta": net,
                        "outcome": outcome.get("outcome"),
                    }
                )
            return history

    async def expire_due(self) -> int:
        self.require_database()
        async with self.session.begin():
            room_ids = list(
                (
                    await self.session.scalars(
                        select(GameRoom.id)
                        .where(
                            GameRoom.game_type == "holdem",
                            GameRoom.ruleset_version == "holdem-v1",
                            GameRoom.deadline_at <= utc(self.rooms.now()),
                            GameRoom.status.in_(["waiting", "active"]),
                        )
                        .order_by(GameRoom.deadline_at, GameRoom.id)
                        .limit(100)
                    )
                ).all()
            )
        processed = 0
        for room_id in room_ids:
            event = None
            try:
                async with _QUEUE_LOCK, self.session.begin():
                    room = await self.rooms._load_db_room(room_id, lock=True)
                    if (
                        room.status not in ("waiting", "active")
                        or room.deadline_at is None
                        or utc(room.deadline_at) > utc(self.rooms.now())
                    ):
                        continue
                    # The row lock plus deterministic ID guards retries after restart.
                    action_id = uuid5(
                        room.id, f"timeout:{room.state_version}:{utc(room.deadline_at).isoformat()}"
                    )
                    members = await self.members(room.id)
                    if room.status == "waiting":
                        room.status = "closed"
                        room.deadline_at = None
                        room.state_json = {
                            **room.state_json,
                            "phase": "cancelled",
                            "search_deadline": None,
                        }
                        user_id, action = members[0], "search_timeout"
                    else:
                        state = decode_state(room.private_state_json["state"])
                        user_id = members[state.current_seat]
                        legal = legal_holdem_actions(
                            state, state.current_seat, rules_for_buy_in(room.state_json["buy_in"])
                        )
                        action = "check" if "check" in legal else "fold"
                        transition = apply_holdem_action(
                            state,
                            state.current_seat,
                            HoldemAction(action),
                            self.rng,
                            rules_for_buy_in(room.state_json["buy_in"]),
                        )
                        await self.update(room, transition.state, action_id)
                    event = await self.record(room, user_id, action_id, action)
            except (
                SQLAlchemyError,
                OSError,
                TimeoutError,
                ValueError,
                KeyError,
                TypeError,
                RuntimeError,
            ) as error:
                # A damaged hand must not stop other rooms. No exception text or private state.
                logging.getLogger(__name__).error(
                    json.dumps(
                        {
                            "event": "holdem_deadline_room_failed",
                            "room_id": str(room_id),
                            "error_type": type(error).__name__,
                        }
                    )
                )
                continue
            await self.rooms.event_bus.publish(event)
            processed += 1
        return processed
