from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

_DOMAIN_SRC = Path(__file__).resolve().parents[2] / "packages" / "domain" / "src"
if str(_DOMAIN_SRC) not in sys.path:
    sys.path.insert(0, str(_DOMAIN_SRC))

from burmaldoza_domain.games.blackjack import Card, make_deck
from burmaldoza_domain.games.holdem import evaluate_best_hand
from burmaldoza_domain.rng import SeededRandomSource


@dataclass(frozen=True, slots=True)
class HoldemSimulationReport:
    trials: int
    seed: int
    ruleset_version: str
    win_rate: float
    tie_rate: float
    loss_rate: float
    equity: float

    def to_dict(self) -> dict[str, int | float | str]:
        return asdict(self)


def run_holdem_simulation(
    hero_cards: tuple[Card, Card],
    villain_range: tuple[tuple[Card, Card], ...],
    board: tuple[Card, ...],
    trials: int,
    seed: int,
) -> HoldemSimulationReport:
    if trials <= 0:
        raise ValueError("trials must be positive")
    if len(board) > 5:
        raise ValueError("board cannot contain more than five cards")
    known = set(hero_cards + board)
    if len(known) != len(hero_cards) + len(board):
        raise ValueError("hero cards and board must be unique")
    eligible_range = tuple(
        hand for hand in villain_range if len(set(hand)) == 2 and not set(hand) & known
    )
    if not eligible_range:
        raise ValueError("villain range has no legal hand")

    rng = SeededRandomSource(seed)
    wins = ties = losses = 0
    for _ in range(trials):
        villain_cards = rng.choice(eligible_range)
        used = known | set(villain_cards)
        remaining = [card for card in make_deck() if card not in used]
        rng.shuffle(remaining)
        complete_board = board + tuple(remaining[: 5 - len(board)])
        hero_rank = evaluate_best_hand((*hero_cards, *complete_board))
        villain_rank = evaluate_best_hand((*villain_cards, *complete_board))
        if hero_rank > villain_rank:
            wins += 1
        elif hero_rank == villain_rank:
            ties += 1
        else:
            losses += 1

    return HoldemSimulationReport(
        trials=trials,
        seed=seed,
        ruleset_version="holdem-skeleton-1",
        win_rate=wins / trials,
        tie_rate=ties / trials,
        loss_rate=losses / trials,
        equity=(wins + ties / 2) / trials,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Hold'em skeleton equity simulation")
    parser.add_argument("--trials", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    report = run_holdem_simulation(
        hero_cards=(Card("A", "spades"), Card("K", "spades")),
        villain_range=((Card("Q", "clubs"), Card("Q", "diamonds")),),
        board=(Card("2", "hearts"), Card("7", "clubs"), Card("9", "diamonds")),
        trials=args.trials,
        seed=args.seed,
    )
    if args.as_json:
        print(json.dumps(report.to_dict(), sort_keys=True))
    else:
        for key, value in report.to_dict().items():
            print(f"{key}: {value}")


if __name__ == "__main__":
    main()
