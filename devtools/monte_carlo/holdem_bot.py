"""Seeded economic sample against an explicit passive check/call baseline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import fmean, pvariance

_DOMAIN_SRC = Path(__file__).resolve().parents[2] / "packages" / "domain" / "src"
if str(_DOMAIN_SRC) not in sys.path:
    sys.path.insert(0, str(_DOMAIN_SRC))

from burmaldoza_domain.games.holdem import (
    HoldemAction,
    HoldemPhase,
    apply_holdem_action,
    create_heads_up_room,
    settle_holdem,
)
from burmaldoza_domain.games.holdem_bot import (
    HOLD_EM_BUY_INS,
    BotObservation,
    choose_bot_action,
    legal_holdem_actions,
    rules_for_buy_in,
)
from burmaldoza_domain.rng import SeededRandomSource


def run_holdem_bot_simulation(trials: int, seed: int) -> dict[str, object]:
    if trials <= 0:
        raise ValueError("trials must be positive")
    tables = []
    for buy_in in HOLD_EM_BUY_INS:
        rng = SeededRandomSource(seed)
        rules = rules_for_buy_in(buy_in)
        nets: list[int] = []
        wins = ties = losses = positive_payouts = 0
        for _ in range(trials):
            state = create_heads_up_room(buy_in, rng, rules)
            turns = 0
            while state.phase not in {HoldemPhase.SHOWDOWN, HoldemPhase.SETTLED}:
                seat = state.current_seat
                legal = legal_holdem_actions(state, seat, rules)
                if seat == 0:
                    action = HoldemAction("check" if "check" in legal else "call")
                else:
                    action = choose_bot_action(BotObservation(
                        hole_cards=state.hole_cards[seat], community_cards=state.community_cards,
                        legal_actions=legal,
                        amount_to_call=state.current_bet - state.street_contributions[seat],
                        stack=state.players[seat].stack,
                        street_contribution=state.street_contributions[seat],
                        current_bet=state.current_bet, big_blind=rules.big_blind, buy_in=buy_in,
                    ), rng)
                state = apply_holdem_action(state, seat, action, rng, rules).state
                turns += 1
                if turns > 100:
                    raise RuntimeError("Hold'em hand exceeded bounded action count")
                if sum(state.stacks) + state.pot != buy_in * 2:
                    raise RuntimeError("Hold'em chips were not conserved")
            settlement = settle_holdem(state)
            payout = state.players[0].stack + settlement.shares[0]
            net = payout - buy_in
            nets.append(net)
            positive_payouts += payout > 0
            if settlement.winner_seats == (0, 1):
                ties += 1
            elif settlement.winner_seats == (0,):
                wins += 1
            else:
                losses += 1
        mean_net = fmean(nets)
        tables.append({
            "buy_in": buy_in, "samples": trials, "seed": seed,
            "mean_player_net_per_hand_jokergem": mean_net,
            "mean_player_net_per_hand_buy_ins": mean_net / buy_in,
            "net_variance_jokergem_squared": pvariance(nets),
            "net_variance_buy_ins_squared": pvariance(nets) / (buy_in * buy_in),
            "win_rate": wins / trials, "tie_rate": ties / trials, "loss_rate": losses / trials,
            "positive_net_rate": sum(net > 0 for net in nets) / trials,
            "positive_wallet_payout_rate": positive_payouts / trials,
        })
    return {
        "ruleset_version": "holdem-v1", "bot_policy_version": "visible-heuristic-v1",
        "player_baseline": "seat 0: check when legal, otherwise call; never fold or raise",
        "bot_seat": 1, "button_seat": 0,
        "net_formula": "ending_player_stack + player_pot_share - table_buy_in",
        "limitations": "Finite seeded sample of this baseline only; not exact RTP or optimal-play expectation.",
        "tables": tables,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=5000, help="samples per table")
    parser.add_argument("--seed", type=int, default=53)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    report = run_holdem_bot_simulation(args.trials, args.seed)
    print(json.dumps(report, indent=2, sort_keys=True) if args.as_json else report)


if __name__ == "__main__":
    main()
