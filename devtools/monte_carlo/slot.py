from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import pvariance

# The repository keeps pure packages in src/ directories and the runner is
# intentionally executable directly from a checkout without installing them.
_DOMAIN_SRC = Path(__file__).resolve().parents[2] / "packages" / "domain" / "src"
if str(_DOMAIN_SRC) not in sys.path:
    sys.path.insert(0, str(_DOMAIN_SRC))

from burmaldoza_domain.games.slot import spin
from burmaldoza_domain.games.slot_ruleset import load_skeleton_config
from burmaldoza_domain.rng import SeededRandomSource


@dataclass(frozen=True, slots=True)
class SlotSimulationReport:
    trials: int
    seed: int
    ruleset_version: str
    rtp: float
    hit_rate: float
    variance: float
    p5_ending_bankroll: float
    p50_ending_bankroll: float
    p95_ending_bankroll: float
    max_drawdown: int

    def to_dict(self) -> dict[str, int | float | str]:
        return asdict(self)


def _percentile(values: list[int], percentile: float) -> float:
    if not values:
        raise ValueError("at least one value is required")
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def run_slot_simulation(config, trials: int, bet: int, seed: int) -> SlotSimulationReport:
    if trials <= 0:
        raise ValueError("trials must be positive")
    if bet <= 0:
        raise ValueError("bet must be positive")

    rng = SeededRandomSource(seed)
    active_paylines = tuple(range(len(config.paylines)))
    bankroll = trials * bet
    ending_bankrolls: list[int] = []
    net_deltas: list[int] = []
    gross_payout = 0
    hit_count = 0
    peak = bankroll
    max_drawdown = 0

    for _ in range(trials):
        outcome = spin(config, bet, active_paylines, rng)
        gross_payout += outcome.gross_payout
        hit_count += bool(outcome.winning_lines)
        net_deltas.append(outcome.net_delta)
        bankroll += outcome.net_delta
        ending_bankrolls.append(bankroll)
        peak = max(peak, bankroll)
        max_drawdown = max(max_drawdown, peak - bankroll)

    return SlotSimulationReport(
        trials=trials,
        seed=seed,
        ruleset_version=config.ruleset_version,
        rtp=gross_payout / (trials * bet),
        hit_rate=hit_count / trials,
        variance=pvariance(net_deltas),
        p5_ending_bankroll=_percentile(ending_bankrolls, 0.05),
        p50_ending_bankroll=_percentile(ending_bankrolls, 0.50),
        p95_ending_bankroll=_percentile(ending_bankrolls, 0.95),
        max_drawdown=max_drawdown,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the slot skeleton Monte Carlo simulation")
    parser.add_argument("--trials", type=int, default=100_000)
    parser.add_argument("--bet", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    report = run_slot_simulation(load_skeleton_config(), args.trials, args.bet, args.seed)
    if args.as_json:
        print(json.dumps(report.to_dict(), sort_keys=True))
    else:
        for key, value in report.to_dict().items():
            print(f"{key}: {value}")


if __name__ == "__main__":
    main()
