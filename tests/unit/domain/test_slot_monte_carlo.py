import pytest
from burmaldoza_domain.games.slot_ruleset import load_skeleton_config

from devtools.monte_carlo.slot import run_slot_simulation


def test_slot_simulation_is_reproducible_and_reports_bankroll_metrics() -> None:
    config = load_skeleton_config()

    first = run_slot_simulation(config, trials=1000, bet=10, seed=42)
    second = run_slot_simulation(config, trials=1000, bet=10, seed=42)

    assert first == second
    report = first.to_dict()
    assert report["trials"] == 1000
    assert report["seed"] == 42
    assert report["ruleset_version"] == "slot-skeleton-1"
    assert {
        "rtp",
        "hit_rate",
        "variance",
        "p5_ending_bankroll",
        "p50_ending_bankroll",
        "p95_ending_bankroll",
        "max_drawdown",
    }.issubset(report)


def test_skeleton_paytable_has_an_exact_expected_gross_multiplier() -> None:
    config = load_skeleton_config()
    symbol_counts = {"A": 5, "B": 4, "C": 3, "W": 1}
    expected_per_line = (
        ((symbol_counts["A"] ** 3 - 1) * 1)
        + ((symbol_counts["B"] ** 3 - 1) * 2)
        + ((symbol_counts["C"] ** 3 - 1) * 3)
        + (symbol_counts["W"] ** 3 * 5)
    ) / 10**3

    assert expected_per_line == pytest.approx(0.333)
    assert expected_per_line * len(config.paylines) == pytest.approx(0.999)


def test_skeleton_rtp_stays_inside_the_configured_confidence_interval() -> None:
    report = run_slot_simulation(load_skeleton_config(), trials=100_000, bet=10, seed=42)

    assert 0.94 <= report.rtp <= 1.06
