"""Durable six-seat matchmaking and personalized no-limit Hold'em tables."""

from __future__ import annotations

import copy
import json
import logging
from dataclasses import asdict
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4, uuid5

from burmaldoza_contracts.common import RoomStatus
from burmaldoza_contracts.events import EventEnvelope
from burmaldoza_contracts.rooms import ActionRequest, RoomSnapshot
from burmaldoza_domain.core import InvalidActionError, StateVersionConflictError
from burmaldoza_domain.economy import LedgerReason
from burmaldoza_domain.games.blackjack import Card
from burmaldoza_domain.games.holdem import HoldemAction, HoldemPhase
from burmaldoza_domain.games.holdem_multiway import (
    MultiwayPlayer,
    MultiwayRules,
    MultiwayState,
    apply_multiway_action,
    create_multiway_hand,
    legal_multiway_actions,
    multiway_raise_bounds,
)
from burmaldoza_domain.games.holdem_pots import settle_multiway
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import GameAction, GamePlayer, GameRoom, GameRound, User
from app.services.holdem_service import _QUEUE_LOCK, HoldemService, utc

RULESET = "holdem-six-1"


def rules_for_table(buy_in: int) -> MultiwayRules:
    return MultiwayRules(buy_in // 20, buy_in // 10)


def encode_multiway_state(state: MultiwayState) -> dict[str, Any]:
    return json.loads(json.dumps(asdict(state)))


def decode_multiway_state(raw: dict[str, Any]) -> MultiwayState:
    data = dict(raw)
    data["players"] = tuple(MultiwayPlayer(**p) for p in raw["players"])
    data["hole_cards"] = tuple(
        (seat, tuple(Card(**c) for c in cards)) for seat, cards in raw["hole_cards"]
    )
    data["community_cards"] = tuple(Card(**c) for c in raw["community_cards"])
    data["deck"] = tuple(Card(**c) for c in raw["deck"])
    data["pending_seats"] = tuple(raw["pending_seats"])
    data["phase"] = HoldemPhase(raw["phase"])
    return MultiwayState(**data)


class HoldemTableService(HoldemService):
    async def create(self, user_id: int, buy_in: int, action_id: UUID) -> RoomSnapshot:
        from app.services.room_service import RoomServiceError

        self.require_database()
        if (
            type(buy_in) is not int
            or buy_in not in (100, 500, 1000)
            or not isinstance(action_id, UUID)
        ):
            raise RoomServiceError("six-player Hold'em requires buy_in 100/500/1000 and action_id")
        async with _QUEUE_LOCK, self.session.begin():
            await self.queue_lock()
            replay = await self.session.get(GameAction, action_id)
            creation = {"mode": "pvp", "buy_in": buy_in, "table_capacity": 6}
            if replay:
                if replay.user_id != user_id or replay.payload_json.get("creation") != creation:
                    raise RoomServiceError("action_id belongs to a different action")
                room = await self.rooms._load_db_room(replay.room_id, lock=True)
                if str(action_id) in room.private_state_json.get("cancelled_creations", []):
                    receipt = room.private_state_json.get("cancelled_receipts", {}).get(
                        str(action_id)
                    )
                    return (
                        RoomSnapshot.model_validate(receipt)
                        if receipt
                        else self.cancelled_snapshot(room)
                    )
                return await self.project_snapshot(room, user_id)
            duplicate = await self.session.scalar(
                select(GameRoom.id)
                .join(GamePlayer)
                .where(
                    GamePlayer.user_id == user_id,
                    GameRoom.game_type == "holdem",
                    GameRoom.mode == "pvp",
                    (GameRoom.status == "active")
                    | (
                        (GameRoom.status == "waiting")
                        & (
                            (GameRoom.ruleset_version == RULESET)
                            | (GameRoom.deadline_at > utc(self.rooms.now()))
                        )
                    ),
                )
                .limit(1)
            )
            if duplicate:
                raise RoomServiceError("player is already searching or playing Hold'em")
            candidates = list(
                (
                    await self.session.scalars(
                        select(GameRoom)
                        .where(
                            GameRoom.ruleset_version == RULESET,
                            GameRoom.status == "waiting",
                            GameRoom.deadline_at > utc(self.rooms.now()),
                            GameRoom.state_json["buy_in"].as_integer() == buy_in,
                        )
                        .order_by(GameRoom.created_at, GameRoom.id)
                        .with_for_update()
                        .limit(100)
                    )
                ).all()
            )
            room = None
            for candidate in candidates:
                if len(await self.members(candidate.id)) < 6:
                    room = candidate
                    break
            if room is None:
                room = GameRoom(
                    id=uuid4(),
                    game_type="holdem",
                    mode="pvp",
                    status="waiting",
                    ruleset_version=RULESET,
                    state_version=0,
                    state_json={"phase": "waiting", "buy_in": buy_in, "capacity": 6},
                    private_state_json={"schema_version": 1, "departed": {}},
                    deadline_at=utc(self.rooms.now()) + timedelta(seconds=60),
                )
                self.session.add(room)
                await self.session.flush()
            members = await self.members(room.id)
            balances = {
                user: (await self.wallet.get_or_create_in_transaction(user)).balance
                for user in sorted({user_id, *members.values()})
            }
            if balances[user_id] < buy_in:
                raise RoomServiceError("insufficient balance for Hold'em buy-in")
            seat = next(seat for seat in range(6) if seat not in members)
            self.session.add(GamePlayer(room_id=room.id, user_id=user_id, seat=seat, stack=buy_in))
            await self.session.flush()
            await self.lobby(room)
            if len(await self.members(room.id)) == 6:
                await self.start(room, action_id)
            event = await self.record(room, user_id, action_id, "create", creation=creation)
            snapshot = await self.project_snapshot(room, user_id)
        await self.rooms.event_bus.publish(event)
        return snapshot

    def cancelled_snapshot(self, room):
        return self.rooms._db_snapshot(room).model_copy(
            update={
                "status": RoomStatus.CLOSED,
                "public_state": {
                    "phase": "cancelled",
                    "capacity": 6,
                    "buy_in": room.state_json["buy_in"],
                    "players": [],
                    "viewer_seat": None,
                    "legal_actions": [],
                    "search_deadline": None,
                    "turn_deadline": None,
                },
            }
        )

    async def lobby(self, room):
        members = await self.members(room.id)
        room.state_json = {
            "phase": "waiting",
            "capacity": 6,
            "buy_in": room.state_json["buy_in"],
            "players": [
                {
                    "seat": seat,
                    "stack": room.state_json["buy_in"],
                    "committed": 0,
                    "street_committed": 0,
                    "folded": False,
                    "all_in": False,
                }
                for seat in members
            ],
            "search_deadline": utc(room.deadline_at).isoformat() if room.deadline_at else None,
            "turn_deadline": None,
            "current_seat": None,
            "community_cards": [],
            "revealed_seats": [],
        }

    async def start(self, room, action_id):
        members = await self.members(room.id)
        buy_in = room.state_json["buy_in"]
        # Lock the whole roster in the same order used by every wallet mutation.
        balances = {
            user: (await self.wallet.get_or_create_in_transaction(user)).balance
            for user in sorted(members.values())
        }
        for _seat, user in list(members.items()):
            if balances[user] < buy_in:
                await self.depart(room, user, "insufficient_balance")
        members = await self.members(room.id)
        if len(members) < 6 and room.deadline_at and utc(room.deadline_at) > utc(self.rooms.now()):
            await self.lobby(room)
            return
        if len(members) < 2:
            if room.deadline_at and utc(room.deadline_at) <= utc(self.rooms.now()):
                room.status = "closed"
                room.deadline_at = None
                await self.lobby(room)
                room.state_json = {**room.state_json, "phase": "cancelled"}
            else:
                await self.lobby(room)
            return
        entry_balances = {}
        for seat, user in sorted(members.items(), key=lambda item: item[1]):
            result = await self.apply_game_delta(
                user_id=user,
                delta=-buy_in,
                reason=LedgerReason.GAME_STAKE,
                reference_id=room.id,
                idempotency_key=uuid5(room.id, f"stake:{user}"),
            )
            entry_balances[str(seat)] = result.balance_after
        seats = list(members)
        self.rng.shuffle(seats)
        state = create_multiway_hand(
            tuple((seat, buy_in) for seat in members), seats[0], self.rng, rules_for_table(buy_in)
        )
        room.private_state_json = {**room.private_state_json, "entry_balances": entry_balances}
        room.status = "active"
        self.session.add(
            GameRound(
                id=room.id,
                room_id=room.id,
                round_no=1,
                bet_amount=buy_in * len(members),
                payout_amount=0,
                status="active",
                idempotency_key=uuid5(room.id, "round"),
                outcome_json={
                    "buy_in": buy_in,
                    "mode": "pvp",
                    "hero_code": None,
                    "ruleset_version": RULESET,
                },
            )
        )
        await self.session.flush()
        await self.update(room, state, action_id)

    async def update(self, room, state, action_id):
        buy_in = room.state_json["buy_in"]
        finished = state.current_seat is None
        revealed = (
            [p.seat for p in state.players if not p.folded]
            if state.phase == HoldemPhase.SHOWDOWN
            else []
        )
        public = {
            "phase": "settled" if finished else "active",
            "capacity": 6,
            "buy_in": buy_in,
            "game_phase": state.phase.value,
            "button_seat": state.button_seat,
            "small_blind_seat": state.small_blind_seat,
            "big_blind_seat": state.big_blind_seat,
            "current_seat": state.current_seat,
            "pot": state.pot,
            "current_bet": state.current_bet,
            "last_full_raise_size": state.last_full_raise_size,
            "small_blind": buy_in // 20,
            "big_blind": buy_in // 10,
            "community_cards": [asdict(c) for c in state.community_cards],
            "players": [
                {
                    "seat": p.seat,
                    "stack": p.stack,
                    "committed": p.committed,
                    "street_committed": p.street_committed,
                    "folded": p.folded,
                    "all_in": p.stack == 0,
                }
                for p in state.players
            ],
            "revealed_seats": revealed,
            "search_deadline": None,
            "legal_actions_by_seat": {
                str(p.seat): list(legal_multiway_actions(state, p.seat, rules_for_table(buy_in)))
                for p in state.players
            },
            "raise_bounds_by_seat": {
                str(p.seat): list(multiway_raise_bounds(state, p.seat, rules_for_table(buy_in)))
                for p in state.players
            },
        }
        if finished:
            settlement = settle_multiway(state)
            awards, refunds = dict(settlement.awards), dict(settlement.refunds)
            cashouts = {
                str(p.seat): p.stack + awards.get(p.seat, 0) + refunds.get(p.seat, 0)
                for p in state.players
            }
            members = await self.members(room.id)
            balances = {}
            await self.lock_wallets(members)
            for seat, user in sorted(members.items(), key=lambda item: item[1]):
                amount = cashouts[str(seat)]
                if amount:
                    await self.apply_game_delta(
                        user_id=user,
                        delta=amount,
                        reason=LedgerReason.GAME_PAYOUT,
                        reference_id=room.id,
                        idempotency_key=uuid5(room.id, f"payout:{user}"),
                    )
                balances[str(seat)] = (await self.wallet.get_or_create_in_transaction(user)).balance
            public["last_result"] = {
                "pots": [
                    {
                        "amount": p.amount,
                        "eligible_seats": list(p.eligible_seats),
                        "winner_seats": list(p.winner_seats),
                        "shares": {str(s): a for s, a in p.shares},
                    }
                    for p in settlement.pots
                ],
                "refunds": {str(s): a for s, a in settlement.refunds},
                "cashouts": cashouts,
                "payouts": cashouts,
                "net_deltas": {seat: amount - buy_in for seat, amount in cashouts.items()},
                "outcome": "showdown" if revealed else "fold",
            }
            room.private_state_json = {**room.private_state_json, "balances": balances}
            room.status = "settled"
            history = await self.session.get(GameRound, room.id)
            history.status = "settled"
            history.payout_amount = sum(cashouts.values())
            history.outcome_json = {**history.outcome_json, **public["last_result"]}
        room.deadline_at = None if finished else utc(self.rooms.now()) + timedelta(seconds=20)
        public["turn_deadline"] = room.deadline_at.isoformat() if room.deadline_at else None
        room.state_json = public
        room.private_state_json = {
            **room.private_state_json,
            "schema_version": 1,
            "state": encode_multiway_state(state),
        }

    async def record(
        self, room, user_id, action_id, action, *, creation=None, request_payload=None
    ):
        room.state_version += 1
        event = EventEnvelope(
            event_id=action_id,
            room_id=room.id,
            state_version=room.state_version,
            type="holdem.action.accepted",
            ruleset_version=RULESET,
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
        receipts = copy.deepcopy(room.private_state_json.get("cancelled_receipts", {}))
        for creation_id in room.private_state_json.get("cancelled_creations", []):
            receipts.setdefault(creation_id, self.cancelled_snapshot(room).model_dump(mode="json"))
        room.private_state_json = {**room.private_state_json, "cancelled_receipts": receipts}
        return event

    async def depart(self, room, user_id, reason):
        departed = copy.deepcopy(room.private_state_json.get("departed", {}))
        departed[str(user_id)] = {"reason": reason}
        creations = list(
            (
                await self.session.scalars(
                    select(GameAction).where(
                        GameAction.room_id == room.id,
                        GameAction.user_id == user_id,
                        GameAction.action_type == "create",
                    )
                )
            ).all()
        )
        cancelled = set(room.private_state_json.get("cancelled_creations", []))
        cancelled.update(str(action.id) for action in creations)
        room.private_state_json = {
            **room.private_state_json,
            "departed": departed,
            "cancelled_creations": sorted(cancelled),
        }
        await self.session.execute(
            delete(GamePlayer).where(GamePlayer.room_id == room.id, GamePlayer.user_id == user_id)
        )
        await self.session.flush()

    async def apply(self, room_id: UUID, user_id: int, request: ActionRequest) -> EventEnvelope:
        from app.services.room_service import RoomServiceError

        self.require_database()
        async with _QUEUE_LOCK, self.session.begin():
            room = await self.rooms._load_db_room(room_id, lock=True)
            replay = await self.session.get(GameAction, request.action_id)
            if replay:
                if (
                    replay.room_id != room_id
                    or replay.user_id != user_id
                    or replay.payload_json.get("request_payload") != request.payload
                ):
                    raise RoomServiceError("action_id belongs to a different action")
                event = self.rooms._event_from_action(room, replay)
                if replay.action_type == "cancel":
                    return event.model_copy(
                        update={
                            "payload": {
                                "action_id": str(request.action_id),
                                "public_state": self.cancelled_snapshot(room).public_state,
                            }
                        }
                    )
                await self.rooms._require_db_member(room_id, user_id)
                return await self.project_event(room, event, user_id)
            await self.rooms._require_db_member(room_id, user_id)
            if room.state_version != request.expected_state_version:
                raise StateVersionConflictError("old room version")
            if request.payload == {"action": "cancel"}:
                if room.status != "waiting":
                    raise RoomServiceError("only waiting search can be cancelled")
                await self.depart(room, user_id, "player_cancelled")
                if not await self.members(room.id):
                    room.status = "closed"
                    room.deadline_at = None
                await self.lobby(room)
                event = await self.record(
                    room, user_id, request.action_id, "cancel", request_payload=request.payload
                )
                projected = event.model_copy(
                    update={
                        "payload": {
                            "action_id": str(request.action_id),
                            "public_state": self.cancelled_snapshot(room).public_state,
                        }
                    }
                )
            else:
                if room.status != "active" or (
                    room.deadline_at and utc(room.deadline_at) <= utc(self.rooms.now())
                ):
                    raise RoomServiceError("hand is inactive or turn expired")
                members = await self.members(room.id)
                seat = next(seat for seat, user in members.items() if user == user_id)
                state = decode_multiway_state(room.private_state_json["state"])
                action = self.validate_action(request.payload)
                try:
                    state = apply_multiway_action(
                        state, seat, action, rules_for_table(room.state_json["buy_in"])
                    ).state
                except (InvalidActionError, ValueError) as error:
                    raise RoomServiceError(str(error)) from error
                await self.update(room, state, request.action_id)
                event = await self.record(
                    room,
                    user_id,
                    request.action_id,
                    action.kind.value,
                    request_payload=request.payload,
                )
                projected = await self.project_event(room, event, user_id)
        await self.rooms.event_bus.publish(event)
        return projected

    async def project_event(
        self, room: GameRoom, event: EventEnvelope, user_id: int
    ) -> EventEnvelope:
        # Only the durable cancelling actor receives this final receipt after departure.
        action = await self.session.get(GameAction, event.event_id)
        if (
            action is not None
            and action.room_id == room.id
            and action.user_id == user_id
            and action.action_type == "cancel"
            and action.payload_json.get("request_payload") == {"action": "cancel"}
        ):
            return event.model_copy(
                update={
                    "payload": {
                        "action_id": str(event.event_id),
                        "public_state": self.cancelled_snapshot(room).public_state,
                    }
                }
            )
        return await super().project_event(room, event, user_id)

    async def project_public(self, room, public, user_id):
        from app.services.room_service import RoomAccessError

        members = await self.members(room.id)
        seat = next((seat for seat, user in members.items() if user == user_id), None)
        if seat is None:
            raise RoomAccessError("user is not a room member")
        result = copy.deepcopy(public)
        result["viewer_seat"] = seat
        result["seat"] = seat
        result["legal_actions"] = result.pop("legal_actions_by_seat", {}).get(
            str(seat), ["cancel"] if public.get("phase") == "waiting" else []
        )
        minimum, maximum = result.pop("raise_bounds_by_seat", {}).get(str(seat), (None, 0))
        result["min_raise_to"] = minimum if "raise" in result["legal_actions"] else None
        result["max_raise_to"] = maximum
        revealed = set(result.pop("revealed_seats", []))
        hands = (
            dict(room.private_state_json.get("state", {}).get("hole_cards", []))
            if public.get("phase") in ("active", "settled")
            else {}
        )
        for player in result.get("players", []):
            target = player["seat"]
            player["cards"] = (
                copy.deepcopy(hands.get(target, []))
                if target == seat or target in revealed
                else ([{"hidden": True}, {"hidden": True}] if hands else [])
            )
            user = await self.session.get(User, members[target]) if target in members else None
            player["nickname"] = f"@{user.username}" if user and user.username else "Живой игрок"
            player["avatar_path"] = (
                f"/api/v1/rooms/{room.id}/players/{target}/avatar" if user else None
            )
        result["hole_cards"] = copy.deepcopy(hands.get(seat, []))
        own = next((p for p in result.get("players", []) if p["seat"] == seat), {})
        result["to_call"] = max(0, result.get("current_bet", 0) - own.get("street_committed", 0))
        balances = room.private_state_json.get(
            "balances" if public.get("phase") == "settled" else "entry_balances", {}
        )
        result["wallet_balance"] = balances.get(str(seat))
        if result.get("last_result"):
            result["last_result"]["balance_after"] = balances.get(str(seat))
        return result

    async def expire_due(self) -> int:
        self.require_database()
        async with self.session.begin():
            ids = list(
                (
                    await self.session.scalars(
                        select(GameRoom.id)
                        .where(
                            GameRoom.ruleset_version == RULESET,
                            GameRoom.status.in_(["waiting", "active"]),
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
                async with _QUEUE_LOCK, self.session.begin():
                    await self.queue_lock()
                    room = await self.rooms._load_db_room(room_id, lock=True)
                    if (
                        room.status not in ("waiting", "active")
                        or room.deadline_at is None
                        or utc(room.deadline_at) > utc(self.rooms.now())
                    ):
                        continue
                    action_id = uuid5(
                        room.id, f"timeout:{room.state_version}:{utc(room.deadline_at).isoformat()}"
                    )
                    members = await self.members(room.id)
                    user_id = next(iter(members.values()))
                    if room.status == "waiting":
                        if len(members) >= 2:
                            await self.start(room, action_id)
                        else:
                            room.status = "closed"
                            room.deadline_at = None
                            room.state_json = {
                                **room.state_json,
                                "phase": "cancelled",
                                "search_deadline": None,
                            }
                    else:
                        state = decode_multiway_state(room.private_state_json["state"])
                        user_id = members[state.current_seat]
                        legal = legal_multiway_actions(
                            state, state.current_seat, rules_for_table(room.state_json["buy_in"])
                        )
                        state = apply_multiway_action(
                            state,
                            state.current_seat,
                            HoldemAction("check" if "check" in legal else "fold"),
                            rules_for_table(room.state_json["buy_in"]),
                        ).state
                        await self.update(room, state, action_id)
                    event = await self.record(room, user_id, action_id, "timeout")
                await self.rooms.event_bus.publish(event)
                processed += 1
            except (
                SQLAlchemyError,
                OSError,
                TimeoutError,
                ValueError,
                KeyError,
                TypeError,
                RuntimeError,
            ) as error:
                logging.getLogger(__name__).error(
                    "holdem_table_deadline_failed room=%s type=%s", room_id, type(error).__name__
                )
        return processed
