from dataclasses import replace

import pytest
from burmaldoza_domain.core import InvalidActionError, StateVersionConflictError
from burmaldoza_domain.games.blackjack import Card
from burmaldoza_domain.games.holdem import (
    HandCategory,
    HoldemAction,
    HoldemActionType,
    HoldemPhase,
    HoldemRules,
    apply_holdem_action,
    create_heads_up_room,
    evaluate_best_hand,
    settle_holdem,
)
from burmaldoza_domain.rng import SeededRandomSource

RULES = HoldemRules()


def c(rank: str, suit: str) -> Card:
    return Card(rank, suit)


def test_evaluator_covers_all_poker_hand_categories() -> None:
    fixtures = [
        ((c("A", "spades"), c("J", "clubs"), c("8", "diamonds"), c("4", "hearts"), c("2", "clubs")), HandCategory.HIGH_CARD),
        ((c("A", "spades"), c("A", "clubs"), c("8", "diamonds"), c("4", "hearts"), c("2", "clubs")), HandCategory.PAIR),
        ((c("A", "spades"), c("A", "clubs"), c("8", "diamonds"), c("8", "hearts"), c("2", "clubs")), HandCategory.TWO_PAIR),
        ((c("A", "spades"), c("A", "clubs"), c("A", "diamonds"), c("8", "hearts"), c("2", "clubs")), HandCategory.THREE_OF_A_KIND),
        ((c("A", "spades"), c("K", "clubs"), c("Q", "diamonds"), c("J", "hearts"), c("10", "clubs")), HandCategory.STRAIGHT),
        ((c("A", "spades"), c("J", "spades"), c("8", "spades"), c("4", "spades"), c("2", "spades")), HandCategory.FLUSH),
        ((c("A", "spades"), c("A", "clubs"), c("A", "diamonds"), c("8", "hearts"), c("8", "clubs")), HandCategory.FULL_HOUSE),
        ((c("A", "spades"), c("A", "clubs"), c("A", "diamonds"), c("A", "hearts"), c("8", "clubs")), HandCategory.FOUR_OF_A_KIND),
        ((c("9", "spades"), c("8", "spades"), c("7", "spades"), c("6", "spades"), c("5", "spades")), HandCategory.STRAIGHT_FLUSH),
    ]

    for cards, category in fixtures:
        assert evaluate_best_hand(cards).category is category


def test_evaluator_handles_ace_low_straight_tiebreakers_and_equal_ties() -> None:
    wheel = evaluate_best_hand(
        (c("A", "spades"), c("2", "clubs"), c("3", "diamonds"), c("4", "hearts"), c("5", "clubs"))
    )
    six_high = evaluate_best_hand(
        (c("6", "spades"), c("5", "clubs"), c("4", "diamonds"), c("3", "hearts"), c("2", "clubs"))
    )

    assert wheel.category is HandCategory.STRAIGHT
    assert wheel.tiebreakers == (5,)
    assert six_high > wheel
    assert evaluate_best_hand(
        (c("A", "spades"), c("K", "clubs"), c("Q", "diamonds"), c("J", "hearts"), c("10", "clubs"))
    ) == evaluate_best_hand(
        (c("A", "hearts"), c("K", "diamonds"), c("Q", "clubs"), c("J", "spades"), c("10", "hearts"))
    )


def test_create_room_posts_heads_up_blinds_and_rotates_button_roles() -> None:
    state = create_heads_up_room(200, SeededRandomSource(42), RULES)

    assert state.button_seat == 0
    assert state.small_blind_seat == 0
    assert state.big_blind_seat == 1
    assert state.pot == 30
    assert state.current_seat == 0
    assert len(state.hole_cards) == 2
    assert all(len(cards) == 2 for cards in state.hole_cards)


def test_check_is_rejected_when_facing_a_bet_and_call_pays_exact_amount() -> None:
    state = create_heads_up_room(200, SeededRandomSource(42), RULES)

    with pytest.raises(InvalidActionError, match="check"):
        apply_holdem_action(state, 0, HoldemAction(HoldemActionType.CHECK), SeededRandomSource(1), RULES)

    transition = apply_holdem_action(
        state, 0, HoldemAction(HoldemActionType.CALL), SeededRandomSource(1), RULES
    )

    assert transition.state.pot == 40
    assert transition.state.contributions == (20, 20)
    assert transition.state.current_seat == 1


def test_minimum_raise_and_state_version_conflict_are_enforced() -> None:
    state = create_heads_up_room(200, SeededRandomSource(42), RULES)

    with pytest.raises(InvalidActionError, match="minimum"):
        apply_holdem_action(
            state, 0, HoldemAction(HoldemActionType.RAISE, 30), SeededRandomSource(1), RULES
        )
    with pytest.raises(StateVersionConflictError):
        apply_holdem_action(
            state,
            0,
            HoldemAction(HoldemActionType.CALL, expected_state_version=99),
            SeededRandomSource(1),
            RULES,
        )

    transition = apply_holdem_action(
        state, 0, HoldemAction(HoldemActionType.RAISE, 40), SeededRandomSource(1), RULES
    )
    assert transition.state.current_bet == 40
    assert transition.state.contributions[0] == 40


def test_call_then_check_advances_to_flop_and_next_street() -> None:
    rng = SeededRandomSource(42)
    state = create_heads_up_room(200, rng, RULES)
    state = apply_holdem_action(state, 0, HoldemAction(HoldemActionType.CALL), rng, RULES).state
    flop = apply_holdem_action(state, 1, HoldemAction(HoldemActionType.CHECK), rng, RULES).state

    assert flop.phase is HoldemPhase.FLOP
    assert len(flop.community_cards) == 3
    assert flop.current_seat == flop.button_seat
    assert flop.current_bet == 0

    flop = apply_holdem_action(flop, 0, HoldemAction(HoldemActionType.CHECK), rng, RULES).state
    turn = apply_holdem_action(flop, 1, HoldemAction(HoldemActionType.CHECK), rng, RULES).state
    assert turn.phase is HoldemPhase.TURN
    assert len(turn.community_cards) == 4


def test_fold_settles_room_and_no_third_seat_exists() -> None:
    state = create_heads_up_room(200, SeededRandomSource(42), RULES)

    with pytest.raises(InvalidActionError, match="seat"):
        apply_holdem_action(
            state, 2, HoldemAction(HoldemActionType.FOLD), SeededRandomSource(1), RULES
        )

    transition = apply_holdem_action(
        state, 0, HoldemAction(HoldemActionType.FOLD), SeededRandomSource(1), RULES
    )

    assert transition.state.phase is HoldemPhase.SETTLED
    assert transition.settlement is not None
    assert transition.settlement.winner_seats == (1,)
    assert sum(transition.settlement.shares) == state.pot


def test_tied_pot_splits_integer_remainder_in_seat_order() -> None:
    state = create_heads_up_room(200, SeededRandomSource(42), RULES)
    state = replace(
        state,
        phase=HoldemPhase.SHOWDOWN,
        community_cards=(
            c("A", "spades"),
            c("K", "spades"),
            c("Q", "diamonds"),
            c("J", "hearts"),
            c("10", "clubs"),
        ),
        hole_cards=(
            (c("2", "clubs"), c("3", "diamonds")),
            (c("4", "clubs"), c("5", "diamonds")),
        ),
        pot=101,
    )

    settlement = settle_holdem(state)

    assert settlement.winner_seats == (0, 1)
    assert settlement.shares == (51, 50)
    assert sum(settlement.shares) == 101
