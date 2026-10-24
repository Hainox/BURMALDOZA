from dataclasses import replace

import pytest
from burmaldoza_domain.core import InvalidActionError
from burmaldoza_domain.games.holdem import HoldemAction, HoldemPhase
from burmaldoza_domain.games.holdem_multiway import (
    MultiwayRules,
    apply_multiway_action,
    create_multiway_hand,
    legal_multiway_actions,
    multiway_raise_bounds,
)
from burmaldoza_domain.rng import SeededRandomSource

RULES = MultiwayRules(5, 10)


@pytest.mark.parametrize("seats", [(0, 1), (0, 1, 2), tuple(range(6)), (0, 2, 5)])
def test_multiplayer_cards_blinds_and_complete_cycle(seats):
    state = create_multiway_hand(
        tuple((seat, 100) for seat in seats), 0, SeededRandomSource(5), RULES
    )
    cards = [card for _, hand in state.hole_cards for card in hand] + list(state.deck)
    assert len(cards) == len(set(cards)) == 52
    assert state.small_blind_seat == (0 if len(seats) == 2 else seats[1])
    assert state.big_blind_seat == (seats[1] if len(seats) == 2 else seats[2])
    seen = set()
    for _ in range(40):
        if state.current_seat is None:
            break
        seen.add(state.current_seat)
        legal = legal_multiway_actions(state, state.current_seat, RULES)
        state = apply_multiway_action(
            state, state.current_seat, HoldemAction("check" if "check" in legal else "call"), RULES
        ).state
    assert state.phase == HoldemPhase.SHOWDOWN
    assert seen == set(seats)
    assert len(state.community_cards) == 5
    assert sum(p.stack + p.committed for p in state.players) == 100 * len(seats)


def test_fold_does_not_end_six_player_hand_and_full_raise_increment():
    state = create_multiway_hand(
        tuple((seat, 100) for seat in range(6)), 0, SeededRandomSource(5), RULES
    )
    state = apply_multiway_action(state, 3, HoldemAction("fold"), RULES).state
    assert state.phase == HoldemPhase.PRE_FLOP
    state = apply_multiway_action(state, 4, HoldemAction("raise", 30), RULES).state
    assert multiway_raise_bounds(state, 5, RULES) == (50, 100)
    with pytest.raises(InvalidActionError):
        apply_multiway_action(state, 5, HoldemAction("raise", 40), RULES)


def test_short_allin_does_not_reopen_but_cumulative_does():
    state = create_multiway_hand(
        tuple((seat, 100) for seat in range(4)), 0, SeededRandomSource(5), RULES
    )
    players = tuple(
        replace(p, acted_to_bet=50, acted_on_full_bet=True) if p.seat == 0 else p
        for p in state.players
    )
    state = replace(state, players=players, current_seat=0, current_bet=60, last_full_raise_size=40)
    assert "raise" not in legal_multiway_actions(state, 0, RULES)
    state = replace(state, current_bet=90)
    assert "raise" in legal_multiway_actions(state, 0, RULES)
    assert multiway_raise_bounds(state, 0, RULES)[0] == 130


def test_allin_runout_conserves_money():
    from burmaldoza_domain.games.holdem_pots import settle_multiway

    state = create_multiway_hand(((0, 100), (1, 60), (2, 20)), 0, SeededRandomSource(3), RULES)
    while state.current_seat is not None:
        seat = state.current_seat
        legal = legal_multiway_actions(state, seat, RULES)
        player = next(p for p in state.players if p.seat == seat)
        action = (
            HoldemAction("raise", player.stack + player.street_committed)
            if "raise" in legal
            else HoldemAction("call" if "call" in legal else "check")
        )
        state = apply_multiway_action(state, seat, action, RULES).state
    result = settle_multiway(state)
    assert sum(dict(result.awards).values()) + sum(dict(result.refunds).values()) == sum(
        p.committed for p in state.players
    )


def test_opening_bet_sets_full_raise_increment():
    state = create_multiway_hand(((0, 100), (1, 100), (2, 100)), 0, SeededRandomSource(5), RULES)
    while state.phase == HoldemPhase.PRE_FLOP:
        legal = legal_multiway_actions(state, state.current_seat, RULES)
        state = apply_multiway_action(
            state, state.current_seat, HoldemAction("check" if "check" in legal else "call"), RULES
        ).state
    state = apply_multiway_action(state, state.current_seat, HoldemAction("raise", 30), RULES).state
    assert multiway_raise_bounds(state, state.current_seat, RULES)[0] == 60


@pytest.mark.parametrize("seed", range(40))
def test_generated_legal_sequences_terminate_and_preserve_chips(seed):
    import random

    from burmaldoza_domain.games.holdem_pots import settle_multiway

    chooser = random.Random(seed)
    seats = tuple(range(2 + seed % 5))
    state = create_multiway_hand(tuple((s, 100) for s in seats), 0, SeededRandomSource(seed), RULES)
    for _ in range(150):
        if state.current_seat is None:
            break
        seat = state.current_seat
        legal = legal_multiway_actions(state, seat, RULES)
        assert legal
        kind = chooser.choice(legal)
        minimum, maximum = multiway_raise_bounds(state, seat, RULES)
        amount = (
            chooser.choice([minimum, maximum])
            if kind == "raise" and minimum <= maximum
            else maximum
            if kind == "raise"
            else None
        )
        state = apply_multiway_action(state, seat, HoldemAction(kind, amount), RULES).state
        assert sum(p.stack + p.committed for p in state.players) == 100 * len(seats)
        assert all(p.stack >= 0 for p in state.players)
        cards = (
            [card for _, hand in state.hole_cards for card in hand]
            + list(state.deck)
            + list(state.community_cards)
        )
        assert len(cards) == len(set(cards)) == 52
    assert state.current_seat is None
    result = settle_multiway(state)
    assert sum(a for _, a in result.awards) + sum(a for _, a in result.refunds) == state.pot


def test_full_raise_after_short_opening_tracks_increment_not_target():
    state = create_multiway_hand(((0, 100), (1, 24), (2, 100)), 0, SeededRandomSource(5), RULES)
    state = apply_multiway_action(state, 0, HoldemAction("raise", 20), RULES).state
    state = apply_multiway_action(state, 1, HoldemAction("call"), RULES).state
    state = apply_multiway_action(state, 2, HoldemAction("call"), RULES).state
    assert state.phase == HoldemPhase.FLOP and state.current_seat == 1
    state = apply_multiway_action(state, 1, HoldemAction("raise", 4), RULES).state
    assert multiway_raise_bounds(state, 2, RULES)[0] == 10
    state = apply_multiway_action(state, 2, HoldemAction("raise", 14), RULES).state
    assert state.last_full_raise_size == 10
    assert multiway_raise_bounds(state, 0, RULES)[0] == 24
