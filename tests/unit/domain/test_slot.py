from pathlib import Path

import pytest
from burmaldoza_domain.games.slot import calculate_payout, spin
from burmaldoza_domain.games.slot_ruleset import load_skeleton_config
from burmaldoza_domain.rng import SeededRandomSource

FIXTURE_PATH = Path(__file__).parents[2] / "fixtures" / "slot_skeleton.json"


def test_spin_returns_three_reels_with_seven_visible_rows() -> None:
    outcome = spin(load_skeleton_config(FIXTURE_PATH), 10, (0, 1, 2), SeededRandomSource(7))

    assert len(outcome.grid) == 3
    assert all(len(reel) == 7 for reel in outcome.grid)
    assert outcome.ruleset_version == "slot-skeleton-1"


def test_spin_rejects_invalid_bets_and_payline_indexes() -> None:
    config = load_skeleton_config(FIXTURE_PATH)

    with pytest.raises(ValueError, match="positive"):
        spin(config, 0, (0,), SeededRandomSource(1))
    with pytest.raises(ValueError, match="payline"):
        spin(config, 10, (3,), SeededRandomSource(1))
    with pytest.raises(ValueError, match="payline"):
        spin(config, 10, (), SeededRandomSource(1))


def test_calculate_payout_matches_only_left_to_right_consecutive_symbols() -> None:
    config = load_skeleton_config(FIXTURE_PATH)
    grid = (
        ("A", "A", "B", "A", "C", "A", "A"),
        ("A", "A", "B", "A", "C", "A", "A"),
        ("A", "A", "C", "A", "B", "A", "A"),
    )

    winning_lines = calculate_payout(config, grid, 10, (0, 1, 2))

    assert [(line.payline_index, line.match_symbol, line.payout) for line in winning_lines] == [
        (0, "A", 10)
    ]


def test_wild_substitutes_for_the_first_non_wild_symbol() -> None:
    config = load_skeleton_config(FIXTURE_PATH)
    grid = (
        ("W", "A", "B", "A", "C", "A", "A"),
        ("A", "A", "B", "A", "C", "A", "A"),
        ("A", "A", "C", "A", "B", "A", "A"),
    )

    winning_lines = calculate_payout(config, grid, 10, (0,))

    assert len(winning_lines) == 1
    assert winning_lines[0].match_symbol == "A"
    assert winning_lines[0].payout == 10


def test_exact_gross_and_net_delta_are_returned_for_three_lines() -> None:
    config = load_skeleton_config(FIXTURE_PATH)

    class FixedStop:
        def randbelow(self, upper: int) -> int:
            assert upper == 10
            return 0

    outcome = spin(config, 10, (0, 1, 2), FixedStop())

    assert outcome.gross_payout == 20
    assert outcome.net_delta == 10
