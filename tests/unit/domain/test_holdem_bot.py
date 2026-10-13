from dataclasses import FrozenInstanceError, fields, replace

import pytest
from burmaldoza_domain.core import InvalidActionError
from burmaldoza_domain.games.blackjack import Card
from burmaldoza_domain.games.holdem import (
    HoldemAction,
    HoldemPhase,
    apply_holdem_action,
    create_heads_up_room,
)
from burmaldoza_domain.games.holdem_bot import (
    HOLD_EM_BUY_INS,
    BotObservation,
    choose_bot_action,
    legal_holdem_actions,
    rules_for_buy_in,
)
from burmaldoza_domain.rng import SeededRandomSource

from devtools.monte_carlo.holdem_bot import run_holdem_bot_simulation


def test_matched_all_in_runs_out_without_zero_stack_turns() -> None:
    from burmaldoza_domain.games.holdem import HoldemRules

    rules = HoldemRules(small_blind=5, big_blind=10)
    rng = SeededRandomSource(42)
    state = create_heads_up_room(100, rng, rules)
    state = apply_holdem_action(state, 0, HoldemAction("raise", 100), rng, rules).state
    transition = apply_holdem_action(state, 1, HoldemAction("call"), rng, rules)
    assert transition.state.phase is HoldemPhase.SHOWDOWN
    assert len(transition.state.community_cards) == 5
    assert transition.state.stacks == (0, 0)
    assert transition.settlement is not None
    assert sum(transition.settlement.shares) == 200


def observation(buy_in: int = 100) -> BotObservation:
    return BotObservation(
        hole_cards=(Card("A", "spades"), Card("A", "clubs")), community_cards=(),
        legal_actions=("fold", "call", "raise"), amount_to_call=5, stack=95,
        street_contribution=5, current_bet=10, big_blind=10, buy_in=buy_in,
    )


def test_observation_is_frozen_and_cannot_expose_hidden_state() -> None:
    value = observation()
    assert {field.name for field in fields(value)} == {
        "hole_cards", "community_cards", "legal_actions", "amount_to_call", "stack",
        "street_contribution", "current_bet", "big_blind", "buy_in",
    }
    assert not hasattr(value, "__dict__")
    with pytest.raises(FrozenInstanceError):
        value.stack = 0  # type: ignore[misc]


@pytest.mark.parametrize("buy_in", HOLD_EM_BUY_INS)
def test_table_rules_and_legal_turns(buy_in: int) -> None:
    rules = rules_for_buy_in(buy_in)
    state = create_heads_up_room(buy_in, SeededRandomSource(3), rules)
    assert rules.small_blind == buy_in // 20
    assert rules.big_blind == buy_in // 10
    assert rules.turn_timeout_seconds == 20
    assert rules.ruleset_version == "holdem-v1"
    assert legal_holdem_actions(state, 0, rules) == ("fold", "call", "raise")
    assert legal_holdem_actions(state, 1, rules) == ()
    assert legal_holdem_actions(state, 2, rules) == ()
    assert legal_holdem_actions(replace(state, phase=HoldemPhase.SETTLED), 0, rules) == ()
    short = replace(state, players=(replace(state.players[0], stack=5), state.players[1]))
    assert legal_holdem_actions(short, 0, rules) == (("fold", "call") if buy_in == 100 else ("fold",))


def test_unsupported_table_is_rejected() -> None:
    with pytest.raises(ValueError):
        rules_for_buy_in(200)


def test_bot_seeded_decisions_and_integer_raise_bounds() -> None:
    value = observation()
    first = choose_bot_action(value, SeededRandomSource(9))
    assert first == choose_bot_action(value, SeededRandomSource(9))
    assert first.kind == "raise"
    assert isinstance(first.amount, int)
    assert value.current_bet + value.big_blind <= first.amount <= value.stack + value.street_contribution
    assert choose_bot_action(replace(value, legal_actions=("fold", "call"), stack=5), SeededRandomSource(9)).kind == "call"
    assert choose_bot_action(replace(value, legal_actions=("fold", "check"), amount_to_call=0), SeededRandomSource(9)).kind == "check"
    assert choose_bot_action(replace(value, legal_actions=("fold",)), SeededRandomSource(9)).kind == "fold"
    with pytest.raises(InvalidActionError):
        choose_bot_action(replace(value, legal_actions=()), SeededRandomSource(9))


def test_under_minimum_all_in_is_excluded_and_rejected() -> None:
    rules = rules_for_buy_in(100)
    rng = SeededRandomSource(4)
    state = create_heads_up_room(100, rng, rules)
    state = apply_holdem_action(state, 0, HoldemAction("raise", 95), rng, rules).state
    assert legal_holdem_actions(state, 1, rules) == ("fold", "call")
    with pytest.raises(InvalidActionError, match="minimum"):
        apply_holdem_action(state, 1, HoldemAction("raise", 100), rng, rules)


def test_bot_strength_uses_own_hand_and_public_board() -> None:
    weak = replace(
        observation(), hole_cards=(Card("2", "clubs"), Card("7", "hearts")),
        amount_to_call=80, current_bet=85,
    )
    assert choose_bot_action(weak, SeededRandomSource(1)).kind == "fold"
    assert choose_bot_action(observation(), SeededRandomSource(1)).kind == "raise"
    public_straight_flush = tuple(Card(rank, "spades") for rank in ("A", "K", "Q", "J", "10"))
    assert choose_bot_action(
        replace(weak, community_cards=public_straight_flush), SeededRandomSource(1)
    ).kind == "raise"


def test_bot_monte_carlo_is_seeded_and_conserves_integer_chips() -> None:
    report = run_holdem_bot_simulation(25, 53)
    assert report == run_holdem_bot_simulation(25, 53)
    assert report["player_baseline"].startswith("seat 0: check")
    for table in report["tables"]:
        assert table["samples"] == 25
        assert table["win_rate"] + table["tie_rate"] + table["loss_rate"] == pytest.approx(1)
        assert -1 <= table["mean_player_net_per_hand_buy_ins"] <= 1
        assert table["net_variance_jokergem_squared"] >= 0
    with pytest.raises(ValueError):
        run_holdem_bot_simulation(0, 53)
