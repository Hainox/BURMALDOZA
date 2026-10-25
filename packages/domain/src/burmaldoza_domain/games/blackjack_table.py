"""Pure shared-deck Blackjack. Every seat plays the same dealer exactly once."""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..core import InvalidActionError
from ..rng import RandomSource
from .blackjack import (
    BlackjackAction,
    BlackjackPhase,
    BlackjackRules,
    BlackjackState,
    Card,
    hand_value,
    make_deck,
    settle_blackjack,
)

RULESET = "blackjack-gfl-table-1"


@dataclass(frozen=True, slots=True)
class TableHand:
    seat: int
    bet: int
    cards: tuple[Card, ...]
    doubled: bool = False
    finished: bool = False


@dataclass(frozen=True, slots=True)
class BlackjackTableState:
    hands: tuple[TableHand, ...]
    dealer_cards: tuple[Card, ...]
    deck: tuple[Card, ...]
    active_seat: int | None
    settled: bool = False
    ruleset_version: str = RULESET


@dataclass(frozen=True, slots=True)
class TableOutcome:
    seat: int
    result: str
    payout: int
    net_delta: int


def _advance(state: BlackjackTableState, rules: BlackjackRules) -> BlackjackTableState:
    active = next((hand.seat for hand in state.hands if not hand.finished), None)
    if active is not None:
        return replace(state, active_seat=active)
    dealer = list(state.dealer_cards)
    deck = list(state.deck)
    # No need to draw when all players bust; reveal the original dealer hand.
    if any(not hand_value(hand.cards).is_bust for hand in state.hands):
        while True:
            value = hand_value(dealer)
            if (
                value.total > 17
                or value.total == 17
                and (not value.soft or rules.dealer_stands_soft_17)
            ):
                break
            if not deck:
                raise InvalidActionError("blackjack table deck is exhausted")
            dealer.append(deck.pop(0))
    return replace(
        state, dealer_cards=tuple(dealer), deck=tuple(deck), active_seat=None, settled=True
    )


def deal_table(
    bets: dict[int, int], rng: RandomSource, rules: BlackjackRules
) -> BlackjackTableState:
    if not 1 <= len(bets) <= 3 or any(
        type(seat) is not int or seat not in range(3) or type(bet) is not int or bet <= 0
        for seat, bet in bets.items()
    ):
        raise ValueError("table requires 1–3 unique seats 0–2 and positive integer bets")
    deck = list(make_deck())
    rng.shuffle(deck)
    hands = tuple(TableHand(seat, bets[seat], (deck.pop(0), deck.pop(0))) for seat in sorted(bets))
    dealer = (deck.pop(0), deck.pop(0))
    dealer_natural = hand_value(dealer).is_blackjack
    hands = tuple(
        replace(hand, finished=dealer_natural or hand_value(hand.cards).is_blackjack)
        for hand in hands
    )
    state = BlackjackTableState(
        hands, dealer, tuple(deck), None, ruleset_version=rules.ruleset_version
    )
    if dealer_natural:
        return replace(state, settled=True)
    return _advance(state, rules)


def apply_table_action(
    state: BlackjackTableState,
    seat: int,
    action: BlackjackAction,
    rng: RandomSource,
    rules: BlackjackRules,
) -> BlackjackTableState:
    if state.settled or seat != state.active_seat or action not in ("hit", "stand", "double"):
        raise InvalidActionError("blackjack action is not available for this seat")
    hand = next((hand for hand in state.hands if hand.seat == seat), None)
    if hand is None or hand.finished:
        raise InvalidActionError("blackjack hand is finished")
    if action == "double" and (not rules.allow_double or len(hand.cards) != 2 or hand.doubled):
        raise InvalidActionError("double is only available on the initial hand")
    deck = state.deck
    if action == "stand":
        updated = replace(hand, finished=True)
    else:
        if not deck:
            raise InvalidActionError("blackjack table deck is exhausted")
        drawn = (*hand.cards, deck[0])
        deck = deck[1:]
        updated = replace(
            hand,
            cards=drawn,
            bet=hand.bet * (2 if action == "double" else 1),
            doubled=action == "double",
            finished=action == "double" or hand_value(drawn).total >= 21,
        )
    return _advance(
        replace(
            state, hands=tuple(updated if h.seat == seat else h for h in state.hands), deck=deck
        ),
        rules,
    )


def settle_table(state: BlackjackTableState, rules: BlackjackRules) -> tuple[TableOutcome, ...]:
    if not state.settled:
        raise InvalidActionError("blackjack table is not ready to settle")
    outcomes = []
    for hand in state.hands:
        solo = BlackjackState(
            phase=BlackjackPhase.SETTLED,
            bet=hand.bet,
            player_cards=hand.cards,
            dealer_cards=state.dealer_cards,
            dealer_hole_hidden=False,
            player_total=hand_value(hand.cards).total,
            dealer_total=hand_value(state.dealer_cards).total,
            state_version=0,
            ruleset_version=state.ruleset_version,
        )
        result = settle_blackjack(solo, rules)
        outcomes.append(TableOutcome(hand.seat, result.result, result.payout, result.net_delta))
    return tuple(outcomes)
