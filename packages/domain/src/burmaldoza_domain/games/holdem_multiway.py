"""Immutable no-limit Hold'em for two to six physical seats; legacy HU is separate."""

from dataclasses import dataclass, replace

from ..core import InvalidActionError, StateVersionConflictError
from ..rng import RandomSource
from .blackjack import Card, make_deck
from .holdem import HoldemAction, HoldemActionType, HoldemPhase


@dataclass(frozen=True, slots=True)
class MultiwayRules:
    small_blind: int
    big_blind: int
    ruleset_version: str = "holdem-six-1"

    def __post_init__(self):
        if (
            type(self.small_blind) is not int
            or type(self.big_blind) is not int
            or not 0 < self.small_blind < self.big_blind
        ):
            raise ValueError("invalid blinds")


@dataclass(frozen=True, slots=True)
class MultiwayPlayer:
    seat: int
    stack: int
    committed: int = 0
    street_committed: int = 0
    folded: bool = False
    acted_to_bet: int | None = None
    acted_on_full_bet: bool = False


@dataclass(frozen=True, slots=True)
class MultiwayState:
    players: tuple[MultiwayPlayer, ...]
    hole_cards: tuple[tuple[int, tuple[Card, ...]], ...]
    button_seat: int
    small_blind_seat: int
    big_blind_seat: int
    current_seat: int | None
    phase: HoldemPhase
    current_bet: int
    last_full_raise_size: int
    pending_seats: tuple[int, ...]
    community_cards: tuple[Card, ...]
    deck: tuple[Card, ...]
    state_version: int = 0
    ruleset_version: str = "holdem-six-1"

    @property
    def pot(self):
        return sum(p.committed for p in self.players)


@dataclass(frozen=True, slots=True)
class MultiwayTransition:
    state: MultiwayState
    settlement: object | None = None


def clockwise(seats, after):
    return tuple(sorted(seats, key=lambda seat: (seat - after - 1) % 6))


def create_multiway_hand(stacks, button_seat, rng: RandomSource, rules: MultiwayRules):
    stacks = tuple(sorted(stacks))
    seats = tuple(seat for seat, _ in stacks)
    if not 2 <= len(stacks) <= 6 or len(set(seats)) != len(seats) or button_seat not in seats:
        raise ValueError("two to six unique seats and a seated button required")
    if any(
        type(seat) is not int
        or not 0 <= seat < 6
        or type(stack) is not int
        or stack < 2 * rules.big_blind
        for seat, stack in stacks
    ):
        raise ValueError("invalid seat or stack")
    order = clockwise(seats, button_seat)
    sb = button_seat if len(seats) == 2 else order[0]
    bb = order[0] if len(seats) == 2 else order[1]
    players = tuple(
        MultiwayPlayer(
            seat,
            stack - (rules.small_blind if seat == sb else rules.big_blind if seat == bb else 0),
            committed=(rules.small_blind if seat == sb else rules.big_blind if seat == bb else 0),
            street_committed=(
                rules.small_blind if seat == sb else rules.big_blind if seat == bb else 0
            ),
        )
        for seat, stack in stacks
    )
    deck = list(make_deck())
    rng.shuffle(deck)
    hands = {seat: [] for seat in seats}
    for _ in range(2):
        for seat in order:
            hands[seat].append(deck.pop(0))
    pending = clockwise(seats, bb)
    return MultiwayState(
        players,
        tuple((seat, tuple(hands[seat])) for seat in seats),
        button_seat,
        sb,
        bb,
        pending[0],
        HoldemPhase.PRE_FLOP,
        rules.big_blind,
        rules.big_blind,
        pending,
        (),
        tuple(deck),
        ruleset_version=rules.ruleset_version,
    )


def _player(state, seat):
    return next((p for p in state.players if p.seat == seat), None)


def _can_raise(state, player):
    return (
        player.acted_to_bet is None
        or not player.acted_on_full_bet
        or state.current_bet - player.acted_to_bet >= state.last_full_raise_size
    )


def multiway_raise_bounds(state, seat, rules):
    player = _player(state, seat)
    if player is None:
        raise InvalidActionError("unknown seat")
    minimum = (
        rules.big_blind
        if state.current_bet < rules.big_blind
        else state.current_bet + state.last_full_raise_size
    )
    return minimum, player.street_committed + player.stack


def legal_multiway_actions(state, seat, rules):
    player = _player(state, seat)
    if (
        player is None
        or state.current_seat != seat
        or state.phase in (HoldemPhase.SHOWDOWN, HoldemPhase.SETTLED)
        or player.folded
        or not player.stack
    ):
        return ()
    debt = state.current_bet - player.street_committed
    legal = ["fold", "call" if debt > 0 else "check"]
    if (
        player.stack > debt
        and _can_raise(state, player)
        and any(not p.folded and p.stack > 0 and p.seat != seat for p in state.players)
    ):
        legal.append("raise")
    return tuple(legal)


def _advance(state, rules):
    alive = [p for p in state.players if not p.folded]
    if len(alive) == 1:
        return replace(state, phase=HoldemPhase.SETTLED, current_seat=None, pending_seats=())
    actors = [p for p in alive if p.stack > 0]
    pending = tuple(seat for seat in state.pending_seats if any(p.seat == seat for p in actors))
    if len(actors) <= 1:
        # A sole actor still owes a decision when an all-in is ahead of their contribution.
        if actors and actors[0].street_committed < state.current_bet:
            return replace(state, current_seat=actors[0].seat, pending_seats=(actors[0].seat,))
        needed = 5 - len(state.community_cards)
        return replace(
            state,
            community_cards=state.community_cards + state.deck[:needed],
            deck=state.deck[needed:],
            phase=HoldemPhase.SHOWDOWN,
            current_seat=None,
            pending_seats=(),
        )
    if pending:
        return replace(state, pending_seats=pending, current_seat=pending[0])
    if state.phase == HoldemPhase.RIVER:
        return replace(state, phase=HoldemPhase.SHOWDOWN, current_seat=None, pending_seats=())
    phase, count = {
        HoldemPhase.PRE_FLOP: (HoldemPhase.FLOP, 3),
        HoldemPhase.FLOP: (HoldemPhase.TURN, 1),
        HoldemPhase.TURN: (HoldemPhase.RIVER, 1),
    }[state.phase]
    pending = clockwise([p.seat for p in actors], state.button_seat)
    return replace(
        state,
        phase=phase,
        community_cards=state.community_cards + state.deck[:count],
        deck=state.deck[count:],
        players=tuple(
            replace(p, street_committed=0, acted_to_bet=None, acted_on_full_bet=False)
            for p in state.players
        ),
        current_bet=0,
        last_full_raise_size=rules.big_blind,
        pending_seats=pending,
        current_seat=pending[0],
    )


def apply_multiway_action(state, seat, action: HoldemAction, rules: MultiwayRules):
    if (
        action.expected_state_version is not None
        and action.expected_state_version != state.state_version
    ):
        raise StateVersionConflictError("old domain version")
    if action.kind.value not in legal_multiway_actions(state, seat, rules):
        raise InvalidActionError("action is not legal for this seat")
    player = _player(state, seat)
    if action.amount is not None and (type(action.amount) is not int or action.amount < 0):
        raise InvalidActionError("amount must be a non-negative integer")
    cost, current_bet, increment = 0, state.current_bet, state.last_full_raise_size
    if action.kind == HoldemActionType.FOLD:
        player = replace(player, folded=True)
    elif action.kind == HoldemActionType.CALL:
        cost = min(player.stack, state.current_bet - player.street_committed)
        if action.amount is not None and action.amount != cost:
            raise InvalidActionError("call amount differs from debt")
    elif action.kind == HoldemActionType.CHECK:
        if action.amount is not None:
            raise InvalidActionError("check does not accept an amount")
    else:
        minimum, maximum = multiway_raise_bounds(state, seat, rules)
        target = action.amount
        if (
            target is None
            or target <= state.current_bet
            or target > maximum
            or (target < minimum and target != maximum)
        ):
            raise InvalidActionError("raise is below minimum or exceeds stack")
        cost = target - player.street_committed
        if target >= minimum:
            # Completing an incomplete opening preserves the minimum full increment;
            # any larger raise tracks the actual increase, rather than the target.
            increment = max(rules.big_blind, target - state.current_bet)
        current_bet = target
    if action.kind == HoldemActionType.FOLD and action.amount is not None:
        raise InvalidActionError("fold does not accept amount")
    player = replace(
        player,
        stack=player.stack - cost,
        committed=player.committed + cost,
        street_committed=player.street_committed + cost,
        acted_to_bet=current_bet,
        acted_on_full_bet=current_bet >= rules.big_blind,
    )
    players = tuple(player if p.seat == seat else p for p in state.players)
    remaining = {s for s in state.pending_seats if s != seat}
    if current_bet > state.current_bet:
        remaining.update(
            p.seat
            for p in players
            if p.seat != seat and not p.folded and p.stack and p.street_committed < current_bet
        )
    pending = clockwise(remaining, seat)
    updated = _advance(
        replace(
            state,
            players=players,
            pending_seats=pending,
            current_bet=current_bet,
            last_full_raise_size=increment,
            state_version=state.state_version + 1,
        ),
        rules,
    )
    settlement = None
    if updated.current_seat is None:
        from .holdem_pots import settle_multiway

        settlement = settle_multiway(updated)
    return MultiwayTransition(updated, settlement)
