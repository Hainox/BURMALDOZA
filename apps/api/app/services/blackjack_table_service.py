"""Durable three-seat Blackjack with one deck/dealer and atomic round settlement."""

from __future__ import annotations

import asyncio
import copy
import json
import logging
from dataclasses import asdict
from datetime import timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4, uuid5

from burmaldoza_contracts.events import EventEnvelope
from burmaldoza_contracts.rooms import ActionRequest, RoomSnapshot
from burmaldoza_domain.core import (
    InsufficientBalanceError,
    InvalidActionError,
    StateVersionConflictError,
)
from burmaldoza_domain.economy import LedgerReason
from burmaldoza_domain.games.blackjack import BlackjackRules, Card, hand_value
from burmaldoza_domain.games.blackjack_table import (
    RULESET,
    BlackjackTableState,
    TableHand,
    apply_table_action,
    deal_table,
    settle_table,
)
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import GameAction, GamePlayer, GameRoom, GameRound, User
from app.services.holdem_service import utc
from app.services.wallet_service import WalletServiceError

if TYPE_CHECKING:
    from app.services.room_service import RoomService

_TABLE_LOCK = asyncio.Lock()
_RULES = BlackjackRules(ruleset_version=RULESET)


def encode_state(state: BlackjackTableState) -> dict[str, Any]:
    return json.loads(json.dumps(asdict(state)))


def decode_state(raw: dict[str, Any]) -> BlackjackTableState:
    data = dict(raw)
    data["hands"] = tuple(
        TableHand(**{**hand, "cards": tuple(Card(**card) for card in hand["cards"])})
        for hand in raw["hands"]
    )
    for name in ("dealer_cards", "deck"):
        data[name] = tuple(Card(**card) for card in raw[name])
    return BlackjackTableState(**data)


class BlackjackTableService:
    def __init__(self, rooms: RoomService) -> None:
        self.rooms = rooms
        self.session = rooms.session
        self.wallet = rooms.wallet_service
        self.rng = rooms.blackjack_rng

    def require_database(self) -> None:
        from app.services.room_service import RoomServiceError

        if self.session is None:
            raise RoomServiceError("shared Blackjack requires durable database storage")

    async def gate(self) -> None:
        # Serialize creation/replay across independent DB sessions in addition to room locks.
        if self.session.get_bind().dialect.name == "postgresql":
            await self.session.execute(text("SELECT pg_advisory_xact_lock(530002)"))

    @staticmethod
    def require_table(room: GameRoom) -> None:
        from app.services.room_service import RoomServiceError

        if room.ruleset_version != RULESET or room.game_type != "blackjack" or room.mode != "table":
            raise RoomServiceError("room is not a supported shared Blackjack table")

    async def members(self, room_id: UUID) -> list[GamePlayer]:
        return list(
            (
                await self.session.scalars(
                    select(GamePlayer)
                    .where(GamePlayer.room_id == room_id)
                    .order_by(GamePlayer.seat)
                )
            ).all()
        )

    async def member(self, room: GameRoom, user_id: int) -> GamePlayer:
        from app.services.room_service import RoomAccessError

        self.require_table(room)
        member = next(
            (
                m
                for m in await self.members(room.id)
                if m.user_id == user_id and m.status != "leaving"
            ),
            None,
        )
        if member is None:
            raise RoomAccessError("user is not a current room member")
        return member

    async def record(
        self, room: GameRoom, user_id: int, action_id: UUID, payload: dict
    ) -> EventEnvelope:
        room.state_version += 1
        event = EventEnvelope(
            event_id=action_id,
            room_id=room.id,
            state_version=room.state_version,
            type="blackjack.table.accepted",
            ruleset_version=RULESET,
            server_time=utc(self.rooms.now()),
            payload={"action_id": str(action_id), "public_state": copy.deepcopy(room.state_json)},
            animation_hint="blackjack.cards.deal.staged",
        )
        record = self.rooms._event_record(event)
        record["request_payload"] = copy.deepcopy(payload)
        self.session.add(
            GameAction(
                id=action_id,
                room_id=room.id,
                user_id=user_id,
                action_type=payload["action"],
                payload_json=record,
                sequence_no=room.state_version,
            )
        )
        await self.session.flush()
        return event

    async def replay(
        self, room_id: UUID | None, user_id: int, action_id: UUID, payload: dict
    ) -> GameAction | None:
        from app.services.room_service import RoomServiceError

        previous = await self.session.get(GameAction, action_id)
        if previous is not None and (
            previous.user_id != user_id
            or previous.payload_json.get("request_payload") != payload
            or room_id is not None
            and previous.room_id != room_id
        ):
            raise RoomServiceError("action_id belongs to a different action")
        return previous

    async def create(self, user_id: int, action_id: UUID) -> RoomSnapshot:
        from app.services.room_service import RoomServiceError

        self.require_database()
        if not isinstance(action_id, UUID):
            raise RoomServiceError("shared table creation requires UUID action_id")
        async with _TABLE_LOCK, self.session.begin():
            await self.gate()
            previous = await self.replay(None, user_id, action_id, {"action": "create"})
            if previous:
                room = await self.rooms._load_db_room(previous.room_id, lock=True)
                return await self.project_snapshot(room, user_id)
            room = GameRoom(
                id=uuid4(),
                game_type="blackjack",
                mode="table",
                status="waiting",
                ruleset_version=RULESET,
                state_version=0,
                state_json={
                    "phase": "lobby",
                    "capacity": 3,
                    "host_seat": 0,
                    "round_id": None,
                    "players": [],
                    "dealer_cards": [],
                    "dealer_total": None,
                    "active_seat": None,
                    "turn_deadline": None,
                },
                private_state_json={"round_no": 0},
            )
            self.session.add(room)
            await self.session.flush()
            self.session.add(
                GamePlayer(room_id=room.id, user_id=user_id, seat=0, status="active", stack=0)
            )
            await self.session.flush()
            await self.refresh_lobby(room)
            event = await self.record(room, user_id, action_id, {"action": "create"})
            snapshot = await self.project_snapshot(room, user_id)
        await self.rooms.event_bus.publish(event)
        return snapshot

    async def join(self, room_id: UUID, user_id: int, action_id: UUID) -> RoomSnapshot:
        from app.services.room_service import RoomServiceError

        self.require_database()
        if not isinstance(action_id, UUID):
            raise RoomServiceError("join requires UUID action_id")
        async with _TABLE_LOCK, self.session.begin():
            await self.gate()
            room = await self.rooms._load_db_room(room_id, lock=True)
            self.require_table(room)
            if room.status == "closed":
                raise RoomServiceError("table is closed")
            previous = await self.replay(room_id, user_id, action_id, {"action": "join"})
            if previous:
                return await self.project_snapshot(room, user_id)
            members = await self.members(room_id)
            existing = next((m for m in members if m.user_id == user_id), None)
            if existing and existing.status == "leaving":
                raise RoomServiceError("leaving participant must wait for round settlement")
            if existing is None:
                seat = next(
                    (seat for seat in range(3) if all(m.seat != seat for m in members)), None
                )
                if seat is None:
                    raise RoomServiceError("shared Blackjack table is full")
                self.session.add(
                    GamePlayer(
                        room_id=room.id, user_id=user_id, seat=seat, status="active", stack=0
                    )
                )
                await self.session.flush()
                await self.refresh_lobby(room)
            event = await self.record(room, user_id, action_id, {"action": "join"})
            snapshot = await self.project_snapshot(room, user_id)
        await self.rooms.event_bus.publish(event)
        return snapshot

    async def refresh_lobby(self, room: GameRoom) -> None:
        public = copy.deepcopy(room.state_json)
        old = {p["seat"]: p for p in public.get("players", [])}
        public["players"] = []
        for member in await self.members(room.id):
            player = old.get(
                member.seat,
                {
                    "seat": member.seat,
                    "cards": [],
                    "total": None,
                    "bet": 0,
                    "ready": False,
                    "outcome": None,
                },
            )
            player["status"] = (
                "leaving" if member.status == "leaving" else player.get("status", "waiting")
            )
            public["players"].append(player)
        staying = [m.seat for m in await self.members(room.id) if m.status != "leaving"]
        if public["host_seat"] not in staying:
            public["host_seat"] = min(staying) if staying else None
        if not staying and room.status != "active":
            room.status = "closed"
            public["phase"] = "closed"
        room.state_json = public

    async def delta(
        self, user_id: int, delta: int, reason: LedgerReason, round_id: UUID, key: UUID
    ) -> None:
        from app.services.room_service import RoomServiceError

        try:
            result = await self.wallet.apply_delta_in_transaction(
                user_id, delta, reason, round_id, key
            )
        except (WalletServiceError, InsufficientBalanceError) as error:
            raise RoomServiceError("Blackjack table ledger operation failed") from error
        if (result.user_id, result.delta, result.reason, result.reference_id) != (
            user_id,
            delta,
            reason,
            round_id,
        ):
            raise RoomServiceError("Blackjack table ledger identity conflict")

    async def lock_wallets(self, members: list[GamePlayer]) -> None:
        for user_id in sorted({m.user_id for m in members}):
            await self.wallet.get_or_create_in_transaction(user_id)

    async def start(self, room: GameRoom, action_id: UUID) -> None:
        from app.services.room_service import RoomServiceError

        members = await self.members(room.id)
        players = room.state_json["players"]
        if not members or not all(p["ready"] for p in players):
            raise RoomServiceError("all seated players must be ready")
        bets = {p["seat"]: p["bet"] for p in players}
        await self.lock_wallets(members)
        for member in members:
            if (await self.wallet.get_or_create_in_transaction(member.user_id)).balance < bets[
                member.seat
            ]:
                raise RoomServiceError("a ready player's balance no longer covers their bet")
        round_no = room.private_state_json.get("round_no", 0) + 1
        round_id = uuid5(room.id, f"round:{round_no}:{action_id}")
        for member in sorted(members, key=lambda m: m.user_id):
            await self.delta(
                member.user_id,
                -bets[member.seat],
                LedgerReason.GAME_STAKE,
                round_id,
                uuid5(round_id, f"stake:{member.user_id}"),
            )
        state = deal_table(bets, self.rng, _RULES)
        room.private_state_json = {
            "round_no": round_no,
            "round_id": str(round_id),
            "roster": {str(m.seat): m.user_id for m in members},
            "state": encode_state(state),
        }
        self.session.add(
            GameRound(
                id=round_id,
                room_id=room.id,
                round_no=round_no,
                bet_amount=sum(bets.values()),
                payout_amount=0,
                status="active",
                idempotency_key=uuid5(round_id, "round"),
                outcome_json={"mode": "table", "bets": {str(s): b for s, b in bets.items()}},
            )
        )
        room.status = "active"
        room.state_json = {**room.state_json, "round_id": str(round_id)}
        await self.session.flush()
        await self.update(room, state)

    async def update(self, room: GameRoom, state: BlackjackTableState) -> None:
        members = await self.members(room.id)
        round_id = UUID(room.private_state_json["round_id"])
        outcomes = {o.seat: asdict(o) for o in settle_table(state, _RULES)} if state.settled else {}
        if state.settled:
            await self.lock_wallets(members)
            roster = room.private_state_json["roster"]
            for seat, user_id in sorted(roster.items(), key=lambda pair: pair[1]):
                payout = outcomes[int(seat)]["payout"]
                if payout:
                    await self.delta(
                        user_id,
                        payout,
                        LedgerReason.GAME_PAYOUT,
                        round_id,
                        uuid5(round_id, f"payout:{user_id}"),
                    )
            round_row = await self.session.get(GameRound, round_id)
            round_row.status = "settled"
            round_row.payout_amount = sum(o["payout"] for o in outcomes.values())
            round_row.outcome_json = {
                **round_row.outcome_json,
                "outcomes": {str(s): o for s, o in outcomes.items()},
                "roster": roster,
            }
            room.status = "settled"
        hands = {hand.seat: hand for hand in state.hands}
        players = []
        for member in members:
            if state.settled and member.status == "leaving":
                await self.session.delete(member)
                continue
            hand = hands.get(member.seat)
            players.append(
                {
                    "seat": member.seat,
                    "cards": [asdict(c) for c in hand.cards] if hand else [],
                    "total": hand_value(hand.cards).total if hand else None,
                    "bet": hand.bet if hand else 0,
                    "status": "leaving"
                    if member.status == "leaving"
                    else "finished"
                    if hand and hand.finished
                    else "playing"
                    if hand
                    else "waiting",
                    "ready": False,
                    "outcome": outcomes.get(member.seat),
                }
            )
        dealer = (
            [asdict(card) for card in state.dealer_cards]
            if state.settled
            else [asdict(state.dealer_cards[0]), {"hidden": True}]
        )
        room.deadline_at = None if state.settled else utc(self.rooms.now()) + timedelta(seconds=20)
        room.private_state_json = {**room.private_state_json, "state": encode_state(state)}
        room.state_json = {
            **room.state_json,
            "phase": "settled" if state.settled else "active",
            "players": players,
            "dealer_cards": dealer,
            "dealer_total": hand_value(state.dealer_cards).total
            if state.settled
            else hand_value(state.dealer_cards[:1]).total,
            "active_seat": state.active_seat,
            "turn_deadline": room.deadline_at.isoformat() if room.deadline_at else None,
        }
        await self.session.flush()
        await self.refresh_lobby(room)

    @staticmethod
    def validate(payload: dict) -> str:
        from app.services.room_service import RoomServiceError

        action = payload.get("action")
        if action not in ("ready", "unready", "start", "hit", "stand", "double", "leave"):
            raise RoomServiceError("unknown shared Blackjack action")
        if action == "ready":
            if (
                set(payload) != {"action", "bet"}
                or type(payload["bet"]) is not int
                or not 25 <= payload["bet"] <= 1_000_000
            ):
                raise RoomServiceError("ready requires integer bet 25–1000000")
        elif set(payload) != {"action"}:
            raise RoomServiceError("unexpected shared Blackjack action fields")
        return action

    async def apply(self, room_id: UUID, user_id: int, request: ActionRequest) -> EventEnvelope:
        from app.services.room_service import RoomServiceError

        self.require_database()
        action = self.validate(request.payload)
        async with _TABLE_LOCK, self.session.begin():
            room = await self.rooms._load_db_room(room_id, lock=True)
            self.require_table(room)
            previous = await self.replay(room_id, user_id, request.action_id, request.payload)
            if previous:
                event = self.rooms._event_from_action(room, previous)
                if action == "leave":
                    return self.leave_receipt(event)
                return await self.project_event(room, event, user_id)
            member = await self.member(room, user_id)
            if room.state_version != request.expected_state_version:
                raise StateVersionConflictError("shared Blackjack action uses old state version")
            if room.status == "closed":
                raise RoomServiceError("table is closed")
            if action in ("ready", "unready", "start"):
                if room.status == "active":
                    raise RoomServiceError("round is already active")
                if action == "start":
                    if member.seat != room.state_json["host_seat"]:
                        raise RoomServiceError("only the table host can start")
                    await self.start(room, request.action_id)
                else:
                    public = copy.deepcopy(room.state_json)
                    player = next(p for p in public["players"] if p["seat"] == member.seat)
                    player["ready"] = action == "ready"
                    if action == "ready":
                        player["bet"] = request.payload["bet"]
                    room.state_json = public
            elif action == "leave":
                roster = room.private_state_json.get("roster", {})
                if room.status == "active" and str(member.seat) in roster:
                    member.status = "leaving"
                else:
                    await self.session.delete(member)
                await self.session.flush()
                await self.refresh_lobby(room)
            else:
                if (
                    room.status != "active"
                    or room.deadline_at is None
                    or utc(room.deadline_at) <= utc(self.rooms.now())
                ):
                    raise RoomServiceError("shared Blackjack turn is inactive or expired")
                state = decode_state(room.private_state_json["state"])
                if member.seat != state.active_seat:
                    raise RoomServiceError("another player is acting")
                hand = next(h for h in state.hands if h.seat == member.seat)
                await self.lock_wallets(await self.members(room.id))
                if action == "double":
                    await self.delta(
                        user_id,
                        -hand.bet,
                        LedgerReason.GAME_STAKE,
                        UUID(room.private_state_json["round_id"]),
                        uuid5(request.action_id, f"double:{user_id}"),
                    )
                try:
                    updated = apply_table_action(state, member.seat, action, self.rng, _RULES)
                except (InvalidActionError, ValueError) as error:
                    raise RoomServiceError(str(error)) from error
                await self.update(room, updated)
            event = await self.record(room, user_id, request.action_id, request.payload)
            projected = (
                self.leave_receipt(event)
                if action == "leave"
                else await self.project_event(room, event, user_id)
            )
        await self.rooms.event_bus.publish(event)
        return projected

    @staticmethod
    def leave_receipt(event: EventEnvelope) -> EventEnvelope:
        return event.model_copy(
            update={
                "payload": {
                    "action_id": str(event.event_id),
                    "public_state": {"phase": "left", "legal_actions": []},
                }
            }
        )

    async def project_public(self, room: GameRoom, public: dict, user_id: int) -> dict:
        member = await self.member(room, user_id)
        result = copy.deepcopy(public)
        result["viewer_seat"] = member.seat
        result["legal_actions"] = ["leave"]
        own = next((p for p in result["players"] if p["seat"] == member.seat), None)
        if result["phase"] in ("lobby", "settled"):
            result["legal_actions"] += ["unready"] if own and own["ready"] else ["ready"]
            if member.seat == result["host_seat"] and all(p["ready"] for p in result["players"]):
                result["legal_actions"].append("start")
        elif result["phase"] == "active" and result["active_seat"] == member.seat:
            result["legal_actions"] += ["hit", "stand"]
            if own and len(own["cards"]) == 2:
                result["legal_actions"].append("double")
        members = {m.seat: m for m in await self.members(room.id)}
        for player in result["players"]:
            current = members.get(player["seat"])
            user = await self.session.get(User, current.user_id) if current else None
            player["nickname"] = f"@{user.username}" if user and user.username else "Игрок без ника"
        result["dealer"] = {
            "cards": copy.deepcopy(result["dealer_cards"]),
            "total": result["dealer_total"],
        }
        result["wallet_balance"] = (await self.wallet.get_or_create_in_transaction(user_id)).balance
        return result

    async def project_snapshot(self, room: GameRoom, user_id: int) -> RoomSnapshot:
        return self.rooms._db_snapshot(room).model_copy(
            update={"public_state": await self.project_public(room, room.state_json, user_id)}
        )

    async def project_event(
        self, room: GameRoom, event: EventEnvelope, user_id: int
    ) -> EventEnvelope:
        payload = copy.deepcopy(event.payload)
        payload["public_state"] = await self.project_public(room, payload["public_state"], user_id)
        return event.model_copy(update={"payload": payload})

    async def expire_due(self) -> int:
        self.require_database()
        async with self.session.begin():
            ids = list(
                (
                    await self.session.scalars(
                        select(GameRoom.id)
                        .where(
                            GameRoom.ruleset_version == RULESET,
                            GameRoom.status == "active",
                            GameRoom.deadline_at <= utc(self.rooms.now()),
                        )
                        .order_by(GameRoom.deadline_at, GameRoom.id)
                        .limit(100)
                    )
                ).all()
            )
        processed = 0
        for room_id in ids:
            try:
                async with _TABLE_LOCK, self.session.begin():
                    room = await self.rooms._load_db_room(room_id, lock=True)
                    if (
                        room.status != "active"
                        or room.deadline_at is None
                        or utc(room.deadline_at) > utc(self.rooms.now())
                    ):
                        continue
                    state = decode_state(room.private_state_json["state"])
                    actor = room.private_state_json["roster"][str(state.active_seat)]
                    action_id = uuid5(
                        room.id, f"timeout:{room.state_version}:{utc(room.deadline_at).isoformat()}"
                    )
                    await self.update(
                        room,
                        apply_table_action(state, state.active_seat, "stand", self.rng, _RULES),
                    )
                    event = await self.record(
                        room, actor, action_id, {"action": "stand", "timeout": True}
                    )
            except (SQLAlchemyError, ValueError, KeyError, TypeError, RuntimeError) as error:
                logging.getLogger(__name__).error(
                    "blackjack_deadline_room_failed room_id=%s error_type=%s",
                    room_id,
                    type(error).__name__,
                )
                continue
            await self.rooms.event_bus.publish(event)
            processed += 1
        return processed
