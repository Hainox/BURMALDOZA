from burmaldoza_domain.games.blackjack import BlackjackRules

from devtools.monte_carlo.blackjack import run_blackjack_simulation


def test_blackjack_simulation_is_reproducible() -> None:
    first = run_blackjack_simulation(1000, 25, 42, "basic-hit-stand")
    second = run_blackjack_simulation(1000, 25, 42, "basic-hit-stand")

    assert first == second
    assert first.trials == 1000
    assert first.ruleset_version == BlackjackRules().ruleset_version
    assert 0 <= first.win_rate <= 1
    assert 0 <= first.push_rate <= 1
    assert 0 <= first.loss_rate <= 1
    assert first.confidence_interval_low <= first.average_net_delta <= first.confidence_interval_high
