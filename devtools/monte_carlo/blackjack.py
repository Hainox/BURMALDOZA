from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import fmean, pvariance

_DOMAIN_SRC = Path(__file__).resolve().parents[2] / "packages" / "domain" / "src"
if str(_DOMAIN_SRC) not in sys.path:
    sys.path.insert(0, str(_DOMAIN_SRC))

from burmaldoza_domain.games.blackjack import (
    BlackjackRules,
    BlackjackState,
    apply_action,
    deal_initial,
    settle_blackjack,
)
from burmaldoza_domain.rng import SeededRandomSource


@dataclass(frozen=True, slots=True)
class BlackjackSimulationReport:
    trials: int
    seed: int
    strategy: str
    ruleset_version: str
    win_rate: float
    push_rate: float
    loss_rate: float
    average_net_delta: float
    variance: float
    confidence_interval_low: float
    confidence_interval_high: float

    def to_dict(self) -> dict[str, int | float | str]:
        return asdict(self)


def _basic_hit_stand(state: BlackjackState) -> str:
    return "hit" if state.player_total < 17 else "stand"


def run_blackjack_simulation(
    trials: int,
    bet: int,
    seed: int,
    strategy: str,
) -> BlackjackSimulationReport:
    if trials <= 0:
        raise ValueError("trials must be positive")
    if bet <= 0:
        raise ValueError("bet must be positive")
    if strategy != "basic-hit-stand":
        raise ValueError("only basic-hit-stand is available in the skeleton")

    rules = BlackjackRules()
    rng = SeededRandomSource(seed)
    net_deltas: list[int] = []
    wins = pushes = losses = 0
    for _ in range(trials):
        state = deal_initial(bet, rng, rules)
        while state.phase.value == "player_turn":
            transition = apply_action(state, _basic_hit_stand(state), rng, rules)
            state = transition.state
        settlement = settle_blackjack(state, rules)
        net_deltas.append(settlement.net_delta)
        if settlement.result in {"win", "blackjack"}:
            wins += 1
        elif settlement.result == "push":
            pushes += 1
        else:
            losses += 1

    average_net_delta = fmean(net_deltas)
    variance = pvariance(net_deltas)
    margin = 1.96 * math.sqrt(variance / trials)
    return BlackjackSimulationReport(
        trials=trials,
        seed=seed,
        strategy=strategy,
        ruleset_version=rules.ruleset_version,
        win_rate=wins / trials,
        push_rate=pushes / trials,
        loss_rate=losses / trials,
        average_net_delta=average_net_delta,
        variance=variance,
        confidence_interval_low=average_net_delta - margin,
        confidence_interval_high=average_net_delta + margin,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Blackjack skeleton Monte Carlo simulation")
    parser.add_argument("--trials", type=int, default=100_000)
    parser.add_argument("--bet", type=int, default=25)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--strategy", default="basic-hit-stand")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    report = run_blackjack_simulation(args.trials, args.bet, args.seed, args.strategy)
    if args.as_json:
        print(json.dumps(report.to_dict(), sort_keys=True))
    else:
        for key, value in report.to_dict().items():
            print(f"{key}: {value}")


if __name__ == "__main__":
    main()
