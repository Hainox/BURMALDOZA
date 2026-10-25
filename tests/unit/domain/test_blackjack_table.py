from dataclasses import replace

import pytest
from burmaldoza_domain.core import InvalidActionError
from burmaldoza_domain.games.blackjack import BlackjackRules, Card, hand_value
from burmaldoza_domain.games.blackjack_table import (
    BlackjackTableState,
    TableHand,
    apply_table_action,
    deal_table,
    settle_table,
)
from burmaldoza_domain.rng import SeededRandomSource

RULES = BlackjackRules(ruleset_version="blackjack-gfl-table-1")


def cards(*ranks):
    return tuple(Card(rank, "clubs") for rank in ranks)


@pytest.mark.parametrize("count", [1, 2, 3])
def test_shared_deal_uses_one_unique_deck(count):
    state = deal_table({seat: 25 for seat in range(count)}, SeededRandomSource(9), RULES)
    all_cards = [card for hand in state.hands for card in hand.cards]
    all_cards += list(state.dealer_cards + state.deck)
    assert len(all_cards) == len(set(all_cards)) == 52
    assert all(len(hand.cards) == 2 for hand in state.hands)
    assert len(state.dealer_cards) >= 2


@pytest.mark.parametrize("bets", [{}, {0: 25, 1: 25, 2: 25, 3: 25}, {0: 0}, {True: 25}, {3: 25}])
def test_invalid_deal_refused(bets):
    with pytest.raises(ValueError):
        deal_table(bets, SeededRandomSource(1), RULES)


def test_dealer_waits_until_every_player_finished():
    state = BlackjackTableState(
        hands=(TableHand(0, 25, cards("10", "7")), TableHand(2, 50, cards("10", "6"))),
        dealer_cards=cards("10", "6"),
        deck=cards("2", "5"),
        active_seat=0,
    )
    next_state = apply_table_action(state, 0, "stand", SeededRandomSource(1), RULES)
    assert next_state.dealer_cards == state.dealer_cards
    assert next_state.active_seat == 2
    settled = apply_table_action(next_state, 2, "double", SeededRandomSource(1), RULES)
    assert settled.settled and settled.active_seat is None
    assert settled.hands[1].bet == 100
    assert len(settled.hands[1].cards) == 3
    assert settled.dealer_cards == cards("10", "6", "5")
    outcomes = settle_table(settled, RULES)
    assert [result.payout for result in outcomes] == [0, 0]
    assert sum(result.net_delta for result in outcomes) == -125


def test_wrong_turn_and_actions_after_settlement_refused():
    state = BlackjackTableState((TableHand(0, 25, cards("10", "7")),), cards("10", "7"), (), 0)
    with pytest.raises(InvalidActionError):
        apply_table_action(state, 2, "stand", SeededRandomSource(1), RULES)
    done = apply_table_action(state, 0, "stand", SeededRandomSource(1), RULES)
    with pytest.raises(InvalidActionError):
        apply_table_action(done, 0, "hit", SeededRandomSource(1), RULES)
    assert settle_table(done, RULES)[0].payout == 25


def test_soft_seventeen_and_odd_natural_payout():
    state = BlackjackTableState(
        (TableHand(0, 25, cards("A", "K"), finished=True),),
        cards("A", "6"),
        cards("10"),
        None,
        True,
    )
    result = settle_table(state, RULES)[0]
    assert (result.result, result.payout, result.net_delta) == ("blackjack", 62, 37)
    assert hand_value(state.dealer_cards).soft


def test_hit_to_bust_skips_to_next_player_without_dealer_draw():
    state = BlackjackTableState(
        (TableHand(0, 25, cards("K", "7")), TableHand(1, 25, cards("9", "7"))),
        cards("10", "6"),
        cards("8", "5"),
        0,
    )
    next_state = apply_table_action(state, 0, "hit", SeededRandomSource(1), RULES)
    assert next_state.active_seat == 1 and next_state.hands[0].finished
    assert next_state.dealer_cards == state.dealer_cards
    with pytest.raises(InvalidActionError):
        settle_table(next_state, RULES)
    with pytest.raises(InvalidActionError):
        apply_table_action(
            replace(next_state, active_seat=0), 0, "double", SeededRandomSource(1), RULES
        )
