from dataclasses import replace

from burmaldoza_domain.games.blackjack import Card
from burmaldoza_domain.games.holdem import HoldemPhase
from burmaldoza_domain.games.holdem_multiway import MultiwayRules, create_multiway_hand
from burmaldoza_domain.games.holdem_pots import settle_multiway
from burmaldoza_domain.rng import SeededRandomSource


def test_sidepots_refund_and_folded_contribution():
    state = create_multiway_hand(
        ((0, 100), (1, 100), (2, 100)), 0, SeededRandomSource(1), MultiwayRules(5, 10)
    )
    hands = (
        (0, (Card("2", "clubs"), Card("3", "diamonds"))),
        (1, (Card("K", "clubs"), Card("K", "diamonds"))),
        (2, (Card("A", "clubs"), Card("A", "diamonds"))),
    )
    board = tuple(
        Card(rank, suit)
        for rank, suit in [
            ("4", "spades"),
            ("6", "clubs"),
            ("8", "hearts"),
            ("J", "spades"),
            ("Q", "hearts"),
        ]
    )
    state = replace(
        state,
        phase=HoldemPhase.SHOWDOWN,
        current_seat=None,
        players=tuple(replace(p, committed=[100, 60, 20][p.seat], stack=0) for p in state.players),
        hole_cards=hands,
        community_cards=board,
    )
    result = settle_multiway(state)
    assert dict(result.refunds) == {0: 40}
    assert dict(result.awards) == {0: 0, 1: 80, 2: 60}
    state = replace(
        state, players=tuple(replace(p, folded=True) if p.seat == 1 else p for p in state.players)
    )
    assert dict(settle_multiway(state).awards) == {0: 80, 1: 0, 2: 60}


def test_odd_chips_start_left_of_button():
    state = create_multiway_hand(
        ((0, 100), (1, 100), (2, 100)), 0, SeededRandomSource(1), MultiwayRules(5, 10)
    )
    board = tuple(Card(rank, "hearts") for rank in ("10", "J", "Q", "K", "A"))
    state = replace(
        state,
        phase=HoldemPhase.SHOWDOWN,
        current_seat=None,
        players=tuple(replace(p, committed=5, folded=p.seat == 1) for p in state.players),
        community_cards=board,
    )
    assert dict(settle_multiway(state).awards) == {0: 7, 1: 0, 2: 8}
