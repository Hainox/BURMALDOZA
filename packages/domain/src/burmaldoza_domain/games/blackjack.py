from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Literal

from ..core import InvalidActionError
from ..rng import RandomSource

BlackjackAction = Literal["hit", "stand", "double"]


class BlackjackPhase(StrEnum):
    PLAYER_TURN = "player_turn"
    DEALER_RESOLUTION = "dealer_resolution"
    SETTLED = "settled"


@dataclass(frozen=True, slots=True)
class Card:
    rank: str
    suit: str

    def __post_init__(self) -> None:
        if self.rank not in {"A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"}:
            raise ValueError("unknown blackjack rank")
        if not self.suit:
            raise ValueError("card suit cannot be empty")


@dataclass(frozen=True, slots=True)
class HandValue:
    total: int
    soft: bool
    is_bust: bool
    is_blackjack: bool


@dataclass(frozen=True, slots=True)
class BlackjackRules:
    blackjack_numerator: int = 3
    blackjack_denominator: int = 2
    dealer_stands_soft_17: bool = True
    allow_double: bool = True
    ruleset_version: str = "blackjack-gfl-skeleton-1"

    def __post_init__(self) -> None:
        if self.blackjack_numerator <= 0 or self.blackjack_denominator <= 0:
            raise ValueError("blackjack payout ratio must be positive")


@dataclass(frozen=True, slots=True)
class BlackjackState:
    phase: BlackjackPhase
    bet: int
    player_cards: tuple[Card, ...]
    dealer_cards: tuple[Card, ...]
    dealer_hole_hidden: bool
    player_total: int
    dealer_total: int
    state_version: int
    ruleset_version: str
    deck: tuple[Card, ...] = ()
    player_natural_blackjack: bool = False
    doubled: bool = False

    def __post_init__(self) -> None:
        if self.bet <= 0:
            raise ValueError("blackjack bet must be positive")
        if self.state_version < 0:
            raise ValueError("state version cannot be negative")


BlackjackResult = Literal["blackjack", "win", "push", "loss"]


@dataclass(frozen=True, slots=True)
class BlackjackSettlement:
    result: BlackjackResult
    payout: int
    net_delta: int
    player_total: int
    dealer_total: int
    ruleset_version: str

    @property
    def gross_payout(self) -> int:
        return self.payout


@dataclass(frozen=True, slots=True)
class BlackjackTransition:
    state: BlackjackState
    action: BlackjackAction
    settlement: BlackjackSettlement | None = None


_RANK_VALUES = {
    "A": 11,
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "10": 10,
    "J": 10,
    "Q": 10,
    "K": 10,
}
_SUITS = ("clubs", "diamonds", "hearts", "spades")
_RANKS = tuple(_RANK_VALUES)


def make_deck() -> tuple[Card, ...]:
    return tuple(Card(rank, suit) for suit in _SUITS for rank in _RANKS)


def hand_value(cards: Sequence[Card]) -> HandValue:
    total = sum(_RANK_VALUES[card.rank] for card in cards)
    aces = sum(card.rank == "A" for card in cards)
    while total > 21 and aces:
        total -= 10
        aces -= 1
    soft = total <= 21 and aces > 0
    return HandValue(
        total=total,
        soft=soft,
        is_bust=total > 21,
        is_blackjack=len(cards) == 2 and total == 21,
    )


def _draw_card(state: BlackjackState, rng: RandomSource) -> tuple[Card, tuple[Card, ...]]:
    deck = list(state.deck)
    if not deck:
        used = set(state.player_cards + state.dealer_cards)
        deck = [card for card in make_deck() if card not in used]
        rng.shuffle(deck)
    if not deck:
        raise InvalidActionError("blackjack deck is exhausted")
    return deck[0], tuple(deck[1:])


def _resolve_dealer(state: BlackjackState, rng: RandomSource, rules: BlackjackRules) -> BlackjackState:
    dealer_cards = list(state.dealer_cards)
    deck = state.deck
    while True:
        value = hand_value(dealer_cards)
        should_hit = value.total < 17 or (
            value.total == 17 and value.soft and not rules.dealer_stands_soft_17
        )
        if value.is_bust or not should_hit:
            break
        draw_state = replace(state, dealer_cards=tuple(dealer_cards), deck=deck)
        drawn, deck = _draw_card(draw_state, rng)
        dealer_cards.append(drawn)
    dealer_value = hand_value(dealer_cards)
    return replace(
        state,
        phase=BlackjackPhase.DEALER_RESOLUTION,
        dealer_cards=tuple(dealer_cards),
        dealer_hole_hidden=False,
        dealer_total=dealer_value.total,
        deck=deck,
    )


def deal_initial(bet: int, rng: RandomSource, rules: BlackjackRules) -> BlackjackState:
    if bet <= 0:
        raise ValueError("blackjack bet must be positive")
    deck = list(make_deck())
    rng.shuffle(deck)
    player_cards = (deck.pop(0), deck.pop(0))
    dealer_cards = (deck.pop(0), deck.pop(0))
    player_value = hand_value(player_cards)
    dealer_value = hand_value(dealer_cards)
    phase = (
        BlackjackPhase.DEALER_RESOLUTION
        if player_value.is_blackjack or dealer_value.is_blackjack
        else BlackjackPhase.PLAYER_TURN
    )
    return BlackjackState(
        phase=phase,
        bet=bet,
        player_cards=player_cards,
        dealer_cards=dealer_cards,
        dealer_hole_hidden=phase is BlackjackPhase.PLAYER_TURN,
        player_total=player_value.total,
        dealer_total=dealer_value.total,
        state_version=0,
        ruleset_version=rules.ruleset_version,
        deck=tuple(deck),
        player_natural_blackjack=player_value.is_blackjack,
    )


def settle_blackjack(state: BlackjackState, rules: BlackjackRules) -> BlackjackSettlement:
    if state.phase is BlackjackPhase.PLAYER_TURN:
        raise InvalidActionError("blackjack is not ready to settle")

    player_value = hand_value(state.player_cards)
    dealer_value = hand_value(state.dealer_cards)
    player_total = player_value.total
    dealer_total = dealer_value.total
    if player_value.is_blackjack and not dealer_value.is_blackjack:
        payout = state.bet + (state.bet * rules.blackjack_numerator // rules.blackjack_denominator)
        result: BlackjackResult = "blackjack"
    elif dealer_value.is_blackjack and not player_value.is_blackjack or player_value.is_bust:
        payout = 0
        result = "loss"
    elif dealer_value.is_bust or player_total > dealer_total:
        payout = state.bet * 2
        result = "win"
    elif player_total == dealer_total:
        payout = state.bet
        result = "push"
    else:
        payout = 0
        result = "loss"
    return BlackjackSettlement(
        result=result,
        payout=payout,
        net_delta=payout - state.bet,
        player_total=player_total,
        dealer_total=dealer_total,
        ruleset_version=state.ruleset_version,
    )


def apply_action(
    state: BlackjackState,
    action: BlackjackAction,
    rng: RandomSource,
    rules: BlackjackRules,
) -> BlackjackTransition:
    if state.phase is not BlackjackPhase.PLAYER_TURN:
        raise InvalidActionError("blackjack action is no longer available")
    if action not in {"hit", "stand", "double"}:
        raise InvalidActionError("unknown blackjack action")

    if action == "stand":
        next_state = _resolve_dealer(
            replace(state, state_version=state.state_version + 1), rng, rules
        )
    else:
        if action == "double":
            if not rules.allow_double:
                raise InvalidActionError("double is disabled")
            if len(state.player_cards) != 2:
                raise InvalidActionError("double is only available on the initial hand")
        drawn, deck = _draw_card(state, rng)
        player_cards = (*state.player_cards, drawn)
        player_value = hand_value(player_cards)
        next_state = replace(
            state,
            bet=state.bet * 2 if action == "double" else state.bet,
            player_cards=player_cards,
            player_total=player_value.total,
            deck=deck,
            doubled=state.doubled or action == "double",
            state_version=state.state_version + 1,
        )
        if player_value.is_bust:
            next_state = replace(
                next_state,
                phase=BlackjackPhase.SETTLED,
                dealer_hole_hidden=False,
            )
        elif action == "double" or player_value.total == 21:
            next_state = _resolve_dealer(next_state, rng, rules)

    settlement = None
    if next_state.phase in {BlackjackPhase.DEALER_RESOLUTION, BlackjackPhase.SETTLED}:
        settlement = settle_blackjack(next_state, rules)
    return BlackjackTransition(state=next_state, action=action, settlement=settlement)
