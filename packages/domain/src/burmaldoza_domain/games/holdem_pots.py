"""Layered pots, uncalled refunds and clockwise odd chips, without wallet I/O."""

from dataclasses import dataclass

from ..core import InvalidActionError
from .holdem import HoldemPhase, evaluate_best_hand
from .holdem_multiway import clockwise


@dataclass(frozen=True, slots=True)
class PotAward:
    amount: int
    eligible_seats: tuple[int, ...]
    winner_seats: tuple[int, ...]
    shares: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class MultiwaySettlement:
    pots: tuple[PotAward, ...]
    refunds: tuple[tuple[int, int], ...]
    awards: tuple[tuple[int, int], ...]


def settle_multiway(state):
    if state.phase not in (HoldemPhase.SHOWDOWN, HoldemPhase.SETTLED):
        raise InvalidActionError("hand is not ready for settlement")
    committed = {p.seat: p.committed for p in state.players}
    totals = sorted(committed.values(), reverse=True)
    refunds = {}
    if totals[0] > totals[1]:
        seat = next(s for s, amount in committed.items() if amount == totals[0])
        refunds[seat] = totals[0] - totals[1]
        committed[seat] = totals[1]
    alive = {p.seat for p in state.players if not p.folded}
    hands = dict(state.hole_cards)
    if len(alive) > 1 and len(state.community_cards) != 5:
        raise InvalidActionError("showdown requires five board cards")
    ranks = (
        {seat: evaluate_best_hand((*hands[seat], *state.community_cards)) for seat in alive}
        if len(alive) > 1
        else {}
    )
    awards = {p.seat: 0 for p in state.players}
    pots, previous = [], 0
    for level in sorted(set(committed.values()) - {0}):
        contributors = {seat for seat, amount in committed.items() if amount >= level}
        amount = (level - previous) * len(contributors)
        eligible = tuple(sorted(contributors & alive))
        if len(alive) == 1:
            eligible = tuple(alive)
        if not eligible:
            raise InvalidActionError("pot has no eligible player")
        best = max((ranks[seat] for seat in eligible), default=None) if len(alive) > 1 else None
        winners = tuple(seat for seat in eligible if best is None or ranks[seat] == best)
        base, remainder = divmod(amount, len(winners))
        shares = {seat: base for seat in winners}
        for seat in clockwise(winners, state.button_seat)[:remainder]:
            shares[seat] += 1
        for seat, share in shares.items():
            awards[seat] += share
        pots.append(PotAward(amount, eligible, winners, tuple(sorted(shares.items()))))
        previous = level
    return MultiwaySettlement(
        tuple(pots), tuple(sorted(refunds.items())), tuple(sorted(awards.items()))
    )
