from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from enum import IntEnum, StrEnum
from itertools import combinations

from ..core import InvalidActionError, StateVersionConflictError
from ..rng import RandomSource
from .blackjack import Card, make_deck


class HoldemActionType(StrEnum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    RAISE = "raise"


class HoldemPhase(StrEnum):
    PRE_FLOP = "pre_flop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"
    SETTLED = "settled"


@dataclass(frozen=True, slots=True)
class HoldemAction:
    kind: HoldemActionType
    amount: int | None = None
    expected_state_version: int | None = None

    def __post_init__(self) -> None:
        if isinstance(self.kind, str):
            object.__setattr__(self, "kind", HoldemActionType(self.kind))
        if self.amount is not None and self.amount < 0:
            raise ValueError("action amount cannot be negative")


@dataclass(frozen=True, slots=True)
class HoldemRules:
    small_blind: int = 10
    big_blind: int = 20
    turn_timeout_seconds: int = 30
    max_players: int = 2
    ruleset_version: str = "holdem-skeleton-1"

    def __post_init__(self) -> None:
        if self.small_blind <= 0 or self.big_blind <= self.small_blind:
            raise ValueError("blind values are invalid")
        if self.turn_timeout_seconds <= 0 or self.max_players != 2:
            raise ValueError("the skeleton supports exactly two players")


@dataclass(frozen=True, slots=True, order=True)
class HandRank:
    category: HandCategory
    tiebreakers: tuple[int, ...]
    best_five: tuple[Card, ...] = field(default=(), compare=False)


class HandCategory(IntEnum):
    HIGH_CARD = 0
    PAIR = 1
    TWO_PAIR = 2
    THREE_OF_A_KIND = 3
    STRAIGHT = 4
    FLUSH = 5
    FULL_HOUSE = 6
    FOUR_OF_A_KIND = 7
    STRAIGHT_FLUSH = 8


@dataclass(frozen=True, slots=True)
class HoldemPlayerState:
    seat: int
    stack: int
    committed: int
    folded: bool = False


@dataclass(frozen=True, slots=True)
class HoldemState:
    button_seat: int
    small_blind_seat: int
    big_blind_seat: int
    current_seat: int
    phase: HoldemPhase
    players: tuple[HoldemPlayerState, HoldemPlayerState]
    hole_cards: tuple[tuple[Card, Card], tuple[Card, Card]]
    community_cards: tuple[Card, ...]
    pot: int
    current_bet: int
    contributions: tuple[int, int]
    street_contributions: tuple[int, int]
    deck: tuple[Card, ...]
    acted_seats: tuple[int, ...]
    state_version: int
    ruleset_version: str
    folded_seat: int | None = None

    def __post_init__(self) -> None:
        if len(self.players) != 2 or len(self.hole_cards) != 2:
            raise ValueError("heads-up state must contain exactly two seats")
        if self.pot < 0 or self.current_bet < 0 or self.state_version < 0:
            raise ValueError("pot, bet and state version cannot be negative")
        if any(value < 0 for value in self.contributions + self.street_contributions):
            raise ValueError("contributions cannot be negative")

    @property
    def button(self) -> int:
        return self.button_seat

    @property
    def stacks(self) -> tuple[int, int]:
        return tuple(player.stack for player in self.players)  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class HoldemSettlement:
    winner_seats: tuple[int, ...]
    shares: tuple[int, int]
    pot: int
    payouts: tuple[int, int]


@dataclass(frozen=True, slots=True)
class HoldemTransition:
    state: HoldemState
    seat: int
    action: HoldemAction
    settlement: HoldemSettlement | None = None


_RANK_VALUES = {
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "10": 10,
    "J": 11,
    "Q": 12,
    "K": 13,
    "A": 14,
}


def _straight_high(values: Sequence[int]) -> int | None:
    unique = set(values)
    if len(unique) != 5:
        return None
    if unique == {14, 2, 3, 4, 5}:
        return 5
    ordered = sorted(unique)
    if ordered[-1] - ordered[0] == 4:
        return ordered[-1]
    return None


def _evaluate_five(cards: tuple[Card, ...]) -> HandRank:
    values = [_RANK_VALUES[card.rank] for card in cards]
    counts = Counter(values)
    grouped = sorted(counts.items(), key=lambda item: (item[1], item[0]), reverse=True)
    flush = len({card.suit for card in cards}) == 1
    straight_high = _straight_high(values)
    if flush and straight_high is not None:
        return HandRank(HandCategory.STRAIGHT_FLUSH, (straight_high,), cards)
    if grouped[0][1] == 4:
        quad = grouped[0][0]
        kicker = grouped[1][0]
        return HandRank(HandCategory.FOUR_OF_A_KIND, (quad, kicker), cards)
    if grouped[0][1] == 3 and grouped[1][1] == 2:
        return HandRank(HandCategory.FULL_HOUSE, (grouped[0][0], grouped[1][0]), cards)
    if flush:
        return HandRank(HandCategory.FLUSH, tuple(sorted(values, reverse=True)), cards)
    if straight_high is not None:
        return HandRank(HandCategory.STRAIGHT, (straight_high,), cards)
    if grouped[0][1] == 3:
        kickers = sorted((value for value, count in grouped[1:] for _ in range(count)), reverse=True)
        return HandRank(HandCategory.THREE_OF_A_KIND, (grouped[0][0], *kickers), cards)
    if grouped[0][1] == 2 and grouped[1][1] == 2:
        pairs = sorted((grouped[0][0], grouped[1][0]), reverse=True)
        return HandRank(HandCategory.TWO_PAIR, (*pairs, grouped[2][0]), cards)
    if grouped[0][1] == 2:
        kickers = sorted((value for value, count in grouped[1:] for _ in range(count)), reverse=True)
        return HandRank(HandCategory.PAIR, (grouped[0][0], *kickers), cards)
    return HandRank(HandCategory.HIGH_CARD, tuple(sorted(values, reverse=True)), cards)


def evaluate_best_hand(cards: Sequence[Card]) -> HandRank:
    if len(cards) < 5:
        raise ValueError("at least five cards are required")
    return max(_evaluate_five(tuple(five)) for five in combinations(cards, 5))


def create_heads_up_room(buy_in: int, rng: RandomSource, rules: HoldemRules) -> HoldemState:
    if buy_in < rules.big_blind * 2:
        raise ValueError("buy-in must cover two big blinds")
    deck = list(make_deck())
    rng.shuffle(deck)
    hole_cards: list[list[Card]] = [[], []]
    for _ in range(2):
        for seat in range(2):
            hole_cards[seat].append(deck.pop(0))

    players = (
        HoldemPlayerState(seat=0, stack=buy_in - rules.small_blind, committed=rules.small_blind),
        HoldemPlayerState(seat=1, stack=buy_in - rules.big_blind, committed=rules.big_blind),
    )
    return HoldemState(
        button_seat=0,
        small_blind_seat=0,
        big_blind_seat=1,
        current_seat=0,
        phase=HoldemPhase.PRE_FLOP,
        players=players,
        hole_cards=(tuple(hole_cards[0]), tuple(hole_cards[1])),  # type: ignore[arg-type]
        community_cards=(),
        pot=rules.small_blind + rules.big_blind,
        current_bet=rules.big_blind,
        contributions=(rules.small_blind, rules.big_blind),
        street_contributions=(rules.small_blind, rules.big_blind),
        deck=tuple(deck),
        acted_seats=(),
        state_version=0,
        ruleset_version=rules.ruleset_version,
    )


def _to_call(state: HoldemState, seat: int) -> int:
    return state.current_bet - state.street_contributions[seat]


def _update_player(state: HoldemState, seat: int, cost: int) -> HoldemState:
    players = list(state.players)
    player = players[seat]
    if cost > player.stack:
        raise InvalidActionError("stack is insufficient for this action")
    players[seat] = replace(
        player,
        stack=player.stack - cost,
        committed=player.committed + cost,
    )
    contributions = list(state.contributions)
    contributions[seat] += cost
    street_contributions = list(state.street_contributions)
    street_contributions[seat] += cost
    return replace(
        state,
        players=tuple(players),  # type: ignore[arg-type]
        contributions=tuple(contributions),  # type: ignore[arg-type]
        street_contributions=tuple(street_contributions),  # type: ignore[arg-type]
        pot=state.pot + cost,
    )


def _draw_board(state: HoldemState, count: int) -> HoldemState:
    if len(state.deck) < count:
        raise InvalidActionError("deck is exhausted")
    return replace(
        state,
        community_cards=state.community_cards + state.deck[:count],
        deck=state.deck[count:],
    )


def _advance_street(state: HoldemState) -> HoldemState:
    next_phase: HoldemPhase
    count: int
    if state.phase is HoldemPhase.PRE_FLOP:
        next_phase, count = HoldemPhase.FLOP, 3
    elif state.phase is HoldemPhase.FLOP:
        next_phase, count = HoldemPhase.TURN, 1
    elif state.phase is HoldemPhase.TURN:
        next_phase, count = HoldemPhase.RIVER, 1
    elif state.phase is HoldemPhase.RIVER:
        return replace(state, phase=HoldemPhase.SHOWDOWN, current_seat=0, acted_seats=())
    else:
        raise InvalidActionError("room cannot advance from this phase")
    advanced = _draw_board(state, count)
    return replace(
        advanced,
        phase=next_phase,
        current_bet=0,
        street_contributions=(0, 0),
        current_seat=state.button_seat,
        acted_seats=(),
    )


def settle_holdem(state: HoldemState) -> HoldemSettlement:
    if state.phase not in {HoldemPhase.SHOWDOWN, HoldemPhase.SETTLED}:
        raise InvalidActionError("holdem room is not ready to settle")
    if state.folded_seat is not None:
        winner_seats = (1 - state.folded_seat,)
    else:
        if len(state.community_cards) != 5:
            raise InvalidActionError("showdown requires five community cards")
        ranks = tuple(
            evaluate_best_hand((*state.hole_cards[seat], *state.community_cards)) for seat in range(2)
        )
        best = max(ranks)
        winner_seats = tuple(seat for seat, rank in enumerate(ranks) if rank == best)
    base_share, remainder = divmod(state.pot, len(winner_seats))
    shares = [0, 0]
    for seat in winner_seats:
        shares[seat] = base_share + (1 if remainder > 0 else 0)
        remainder -= 1
    return HoldemSettlement(
        winner_seats=winner_seats,
        shares=(shares[0], shares[1]),
        pot=state.pot,
        payouts=(shares[0], shares[1]),
    )


def apply_holdem_action(
    state: HoldemState,
    seat: int,
    action: HoldemAction,
    rng: RandomSource,
    rules: HoldemRules,
) -> HoldemTransition:
    if seat not in (0, 1):
        raise InvalidActionError("seat must be 0 or 1")
    if action.expected_state_version is not None and action.expected_state_version != state.state_version:
        raise StateVersionConflictError("holdem action uses an old state version")
    if state.phase in {HoldemPhase.SHOWDOWN, HoldemPhase.SETTLED}:
        raise InvalidActionError("holdem room is already settled")
    if seat != state.current_seat:
        raise InvalidActionError("action is out of turn")

    to_call = _to_call(state, seat)
    if action.kind is HoldemActionType.FOLD:
        next_state = replace(
            state,
            phase=HoldemPhase.SETTLED,
            folded_seat=seat,
            current_seat=1 - seat,
            state_version=state.state_version + 1,
        )
    else:
        if action.kind is HoldemActionType.CHECK:
            if to_call != 0:
                raise InvalidActionError("check is not legal while facing a bet")
            cost = 0
            next_bet = state.current_bet
            reset_acted = False
        elif action.kind is HoldemActionType.CALL:
            if to_call <= 0:
                raise InvalidActionError("call is not legal without a bet")
            if action.amount is not None and action.amount != to_call:
                raise InvalidActionError("call amount does not match the amount to call")
            cost = to_call
            next_bet = state.current_bet
            reset_acted = False
        elif action.kind is HoldemActionType.RAISE:
            if action.amount is None:
                raise InvalidActionError("raise amount is required")
            minimum = state.current_bet + rules.big_blind
            if action.amount < minimum:
                raise InvalidActionError("raise is below the minimum")
            if action.amount <= state.street_contributions[seat]:
                raise InvalidActionError("raise must increase the player's contribution")
            cost = action.amount - state.street_contributions[seat]
            next_bet = action.amount
            reset_acted = True
        else:
            raise InvalidActionError("unknown holdem action")

        next_state = _update_player(state, seat, cost)
        next_state = replace(
            next_state,
            current_bet=next_bet,
            current_seat=1 - seat,
            acted_seats=(seat,) if reset_acted else tuple(sorted(set(state.acted_seats) | {seat})),
            state_version=state.state_version + 1,
        )
        if (
            len(next_state.acted_seats) == 2
            and next_state.street_contributions[0] == next_state.street_contributions[1]
        ):
            next_state = _advance_street(next_state)

    settlement = None
    if next_state.phase in {HoldemPhase.SHOWDOWN, HoldemPhase.SETTLED}:
        settlement = settle_holdem(next_state)
    return HoldemTransition(state=next_state, seat=seat, action=action, settlement=settlement)
