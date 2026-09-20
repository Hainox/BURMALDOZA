from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from ..rng import RandomSource


@dataclass(frozen=True, slots=True)
class SlotConfig:
    columns: int
    rows: int
    reel_strips: tuple[tuple[str, ...], ...]
    paylines: tuple[tuple[int, ...], ...]
    paytable: Mapping[tuple[str, int], int]
    wild_symbol: str | None
    ruleset_version: str = "slot-skeleton-1"

    def __post_init__(self) -> None:
        if self.columns <= 0 or self.rows <= 0:
            raise ValueError("slot dimensions must be positive")
        if len(self.reel_strips) != self.columns:
            raise ValueError("reel strip count must equal columns")
        if any(len(strip) < self.rows for strip in self.reel_strips):
            raise ValueError("each reel strip must contain all visible rows")
        if not self.paylines:
            raise ValueError("at least one payline is required")
        if any(len(line) != self.columns for line in self.paylines):
            raise ValueError("each payline must contain one row per column")
        if any(row < 0 or row >= self.rows for line in self.paylines for row in line):
            raise ValueError("payline row is outside the visible grid")
        if any(multiplier < 0 for multiplier in self.paytable.values()):
            raise ValueError("payout multipliers cannot be negative")
        symbols = {symbol for strip in self.reel_strips for symbol in strip}
        if self.wild_symbol is not None and self.wild_symbol not in symbols:
            raise ValueError("wild symbol must exist on a reel")
        object.__setattr__(self, "reel_strips", tuple(tuple(strip) for strip in self.reel_strips))
        object.__setattr__(self, "paylines", tuple(tuple(line) for line in self.paylines))
        object.__setattr__(self, "paytable", MappingProxyType(dict(self.paytable)))


@dataclass(frozen=True, slots=True)
class WinningLine:
    payline_index: int
    symbols: tuple[str, ...]
    match_symbol: str
    matched_columns: int
    payout: int


@dataclass(frozen=True, slots=True)
class SlotOutcome:
    grid: tuple[tuple[str, ...], ...]
    winning_lines: tuple[WinningLine, ...]
    gross_payout: int
    net_delta: int
    ruleset_version: str


def _validate_active_paylines(config: SlotConfig, active_paylines: tuple[int, ...]) -> None:
    if not active_paylines:
        raise ValueError("at least one payline must be active")
    if len(set(active_paylines)) != len(active_paylines):
        raise ValueError("active paylines cannot contain duplicates")
    if any(index < 0 or index >= len(config.paylines) for index in active_paylines):
        raise ValueError("payline index is invalid")


def _validate_grid(config: SlotConfig, grid: tuple[tuple[str, ...], ...]) -> None:
    if len(grid) != config.columns or any(len(column) != config.rows for column in grid):
        raise ValueError("grid dimensions do not match slot configuration")


def calculate_payout(
    config: SlotConfig,
    grid: tuple[tuple[str, ...], ...],
    bet: int,
    active_paylines: tuple[int, ...],
) -> tuple[WinningLine, ...]:
    """Evaluate configured paylines from the leftmost reel only."""

    if bet <= 0:
        raise ValueError("bet must be positive")
    _validate_grid(config, grid)
    _validate_active_paylines(config, active_paylines)

    winning_lines: list[WinningLine] = []
    for payline_index in active_paylines:
        payline = config.paylines[payline_index]
        symbols = tuple(grid[column][row] for column, row in enumerate(payline))
        wild = config.wild_symbol
        match_symbol = next((symbol for symbol in symbols if symbol != wild), wild)
        if match_symbol is None:
            continue

        matched_columns = 0
        for symbol in symbols:
            if symbol == match_symbol or (wild is not None and symbol == wild):
                matched_columns += 1
            else:
                break
        if matched_columns != config.columns:
            continue

        multiplier = config.paytable.get((match_symbol, matched_columns))
        if multiplier is None:
            continue
        winning_lines.append(
            WinningLine(
                payline_index=payline_index,
                symbols=symbols,
                match_symbol=match_symbol,
                matched_columns=matched_columns,
                payout=bet * multiplier,
            )
        )
    return tuple(winning_lines)


def spin(
    config: SlotConfig,
    bet: int,
    active_paylines: tuple[int, ...],
    rng: RandomSource,
) -> SlotOutcome:
    """Choose server-side stops and return the confirmed slot outcome."""

    if bet <= 0:
        raise ValueError("bet must be positive")
    _validate_active_paylines(config, active_paylines)

    grid: list[tuple[str, ...]] = []
    for reel_strip in config.reel_strips:
        stop = rng.randbelow(len(reel_strip))
        grid.append(tuple(reel_strip[(stop + row) % len(reel_strip)] for row in range(config.rows)))

    immutable_grid = tuple(grid)
    winning_lines = calculate_payout(config, immutable_grid, bet, active_paylines)
    gross_payout = sum(line.payout for line in winning_lines)
    return SlotOutcome(
        grid=immutable_grid,
        winning_lines=winning_lines,
        gross_payout=gross_payout,
        net_delta=gross_payout - bet,
        ruleset_version=config.ruleset_version,
    )
