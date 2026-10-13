import json
from collections import Counter
from itertools import product

import pytest
from burmaldoza_domain.games.slot import calculate_payout, spin
from burmaldoza_domain.games.slot_ruleset import load_skeleton_config, load_slot_config
from burmaldoza_domain.rng import SeededRandomSource

from devtools.monte_carlo.slot import main, run_slot_simulation


def test_ruleset_registry_preserves_skeleton_and_defaults_to_siege() -> None:
    assert load_slot_config().ruleset_version == "slot-siege-1"
    assert load_slot_config("slot-skeleton-1") == load_skeleton_config()


@pytest.mark.parametrize("version", ["unknown", "../slot_skeleton.json", "", "slot-siege-2"])
def test_ruleset_registry_rejects_unknown_versions(version: str) -> None:
    with pytest.raises(ValueError, match="unknown slot ruleset"):
        load_slot_config(version)


def test_siege_dimensions_counts_and_paytable_match_approved_rules() -> None:
    config = load_slot_config()
    assert (config.columns, config.rows) == (3, 7)
    assert config.paylines == ((3, 3, 3), (2, 3, 4), (4, 3, 2))
    assert config.wild_symbol == "W"
    counts = {"D1": 9, "D2": 6, "D3": 4, "D4": 3, "A1": 2, "A2": 2, "A3": 1, "W": 3}
    assert all(len(strip) == 30 and Counter(strip) == counts for strip in config.reel_strips)
    assert config.paytable == {
        (symbol, 3): multiplier
        for symbol, multiplier in zip(counts, (1, 2, 3, 4, 8, 10, 20, 50), strict=True)
    }


@pytest.mark.parametrize(
    ("symbol", "multiplier"),
    [("D1", 1), ("D2", 2), ("D3", 3), ("D4", 4), ("A1", 8), ("A2", 10), ("A3", 20), ("W", 50)],
)
@pytest.mark.parametrize("wild_columns", [(), (0,), (1,), (2,), (0, 1), (0, 2), (1, 2)])
def test_siege_pays_each_symbol_with_wild_substitution(
    symbol: str, multiplier: int, wild_columns: tuple[int, ...]
) -> None:
    config = load_slot_config()
    grid = tuple(("W" if column in wild_columns else symbol,) * 7 for column in range(3))
    lines = calculate_payout(config, grid, 10, (0, 1, 2))
    assert len(lines) == 3
    assert all(line.match_symbol == symbol and line.payout == 10 * multiplier for line in lines)


def test_siege_mixed_nonwild_symbols_do_not_pay() -> None:
    grid = tuple((symbol,) * 7 for symbol in ("D1", "W", "D2"))
    assert calculate_payout(load_slot_config(), grid, 10, (0, 1, 2)) == ()


def test_siege_spin_wraps_reels_and_reports_server_stops() -> None:
    config = load_slot_config()

    class FixedStops:
        def __init__(self) -> None:
            self.stops = iter((29, 27, 28))

        def randbelow(self, upper: int) -> int:
            assert upper == 30
            return next(self.stops)

    outcome = spin(config, 10, (0, 1, 2), FixedStops())
    assert outcome.reel_stops == (29, 27, 28)
    assert outcome.grid == tuple(
        tuple(strip[(stop + row) % 30] for row in range(7))
        for strip, stop in zip(config.reel_strips, outcome.reel_stops, strict=True)
    )
    assert outcome.ruleset_version == "slot-siege-1"
    assert outcome.net_delta == outcome.gross_payout - 10


def test_siege_exact_rtp_from_actual_engine_with_all_wild_paid_once() -> None:
    config = load_slot_config()
    counts = [Counter(strip) for strip in config.reel_strips]
    weighted_payout = 0
    weighted_hits = 0
    # Uniform independent stops give each line the same symbol shares. Exhaustively
    # evaluate combinations through the engine, including WWW exactly once.
    for symbols in product(*(count.keys() for count in counts)):
        weight = 1
        for count, symbol in zip(counts, symbols, strict=True):
            weight *= count[symbol]
        grid = tuple((symbol,) * config.rows for symbol in symbols)
        lines = calculate_payout(config, grid, 1, (0,))
        weighted_payout += weight * sum(line.payout for line in lines)
        weighted_hits += weight * bool(lines)
    assert weighted_payout == 8663
    rtp = weighted_payout * len(config.paylines) / 30**3
    assert rtp == pytest.approx(0.9625555555555556)
    assert round(rtp, 4) == 0.9626
    assert round(weighted_hits / 30**3, 4) == 0.1173


def test_siege_simulation_is_seeded_and_returns_new_ruleset() -> None:
    config = load_slot_config()
    first = run_slot_simulation(config, trials=1000, bet=10, seed=42)
    assert first == run_slot_simulation(config, trials=1000, bet=10, seed=42)
    assert first.ruleset_version == "slot-siege-1"
    assert spin(config, 10, (0,), SeededRandomSource(42)).ruleset_version == "slot-siege-1"


@pytest.mark.parametrize("version", [None, "slot-skeleton-1", "slot-siege-1"])
def test_monte_carlo_cli_preserves_default_and_selects_ruleset(
    version: str | None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = ["slot", "--trials", "1000", "--seed", "42", "--bet", "10", "--json"]
    if version is not None:
        argv.extend(("--ruleset", version))
    monkeypatch.setattr("sys.argv", argv)
    main()
    selected_version = version or "slot-skeleton-1"
    expected = run_slot_simulation(load_slot_config(selected_version), 1000, 10, 42)
    assert json.loads(capsys.readouterr().out) == expected.to_dict()


def test_monte_carlo_cli_rejects_unknown_ruleset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["slot", "--ruleset", "../slot_skeleton.json"])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
