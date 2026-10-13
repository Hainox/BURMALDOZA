"""Bounded heuristic policy: table selects aggression; character is cosmetic.

This policy is not an equity solver. Preflop strength uses pair/high cards,
suitedness and connectivity; postflop uses only the best visible hand category.
Higher tables bluff/raise more frequently. Calls are capped by visible strength
and a table-specific fraction of the initial stack. Raises are one or two big
blinds above the current bet, capped by the available stack.
"""

from dataclasses import dataclass

from ..core import InvalidActionError
from ..rng import RandomSource
from .blackjack import Card
from .holdem import (
    HoldemAction,
    HoldemPhase,
    HoldemRules,
    HoldemState,
    evaluate_best_hand,
)

HOLD_EM_BUY_INS = (100, 500, 1000)
_VALUES = {rank: value for value, rank in enumerate(
    ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"), 2
)}


def rules_for_buy_in(buy_in: int) -> HoldemRules:
    if buy_in not in HOLD_EM_BUY_INS:
        raise ValueError("unsupported Hold'em buy-in")
    return HoldemRules(
        small_blind=buy_in // 20, big_blind=buy_in // 10,
        turn_timeout_seconds=20, ruleset_version="holdem-v1",
    )


def legal_holdem_actions(state: HoldemState, seat: int, rules: HoldemRules) -> tuple[str, ...]:
    if seat not in (0, 1) or seat != state.current_seat:
        return ()
    if state.phase in {HoldemPhase.SHOWDOWN, HoldemPhase.SETTLED}:
        return ()
    player = state.players[seat]
    if player.folded or player.stack == 0:
        return ()
    amount_to_call = state.current_bet - state.street_contributions[seat]
    actions = ["fold"]
    if amount_to_call == 0:
        actions.append("check")
    elif amount_to_call <= player.stack:
        actions.append("call")
    if state.current_bet + rules.big_blind <= state.street_contributions[seat] + player.stack:
        actions.append("raise")
    return tuple(actions)


@dataclass(frozen=True, slots=True)
class BotObservation:
    # Deliberately excludes opponent cards, deck and the full domain state.
    hole_cards: tuple[Card, Card]
    community_cards: tuple[Card, ...]
    legal_actions: tuple[str, ...]
    amount_to_call: int
    stack: int
    street_contribution: int
    current_bet: int
    big_blind: int
    buy_in: int


def _visible_strength(observation: BotObservation) -> int:
    if observation.community_cards:
        rank = evaluate_best_hand((*observation.hole_cards, *observation.community_cards))
        return min(100, int(rank.category) * 20 + rank.tiebreakers[0] * 2)
    first, second = observation.hole_cards
    high, low = sorted((_VALUES[first.rank], _VALUES[second.rank]), reverse=True)
    if high == low:
        return 50 + high * 3
    return min(100, high * 3 + low + (8 if first.suit == second.suit else 0)
               + (5 if high - low == 1 else 0))


def choose_bot_action(observation: BotObservation, rng: RandomSource) -> HoldemAction:
    table = HOLD_EM_BUY_INS.index(observation.buy_in)
    strength = _visible_strength(observation)
    roll = rng.randbelow(100)
    if "raise" in observation.legal_actions and (
        strength >= 65 - table * 5 or roll < 3 + table * 3
    ):
        minimum = observation.current_bet + observation.big_blind
        maximum = observation.street_contribution + observation.stack
        amount = min(maximum, minimum + (observation.big_blind if strength >= 85 else 0))
        return HoldemAction("raise", amount)
    if "call" in observation.legal_actions:
        # Even weak hands defend a small blind-sized bet; stronger hands pay more.
        cap = max(observation.big_blind, observation.buy_in * (strength + table * 5) // 100)
        if observation.amount_to_call <= cap:
            return HoldemAction("call")
    if "check" in observation.legal_actions:
        return HoldemAction("check")
    if "fold" in observation.legal_actions:
        return HoldemAction("fold")
    raise InvalidActionError("bot has no legal action")
