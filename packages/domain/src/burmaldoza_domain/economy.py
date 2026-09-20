from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .core import InsufficientBalanceError

CURRENCY_CODE = "JOKERGEM"


class LedgerReason(StrEnum):
    WELCOME = "welcome"
    DAILY_BONUS = "daily_bonus"
    RELIEF = "relief"
    GAME_STAKE = "game_stake"
    GAME_PAYOUT = "game_payout"
    ADMIN_ADJUSTMENT = "admin_adjustment"


@dataclass(frozen=True, slots=True)
class EconomyConfig:
    welcome_grant: int = 1000
    daily_bonus: int = 250
    relief_grant: int = 300
    relief_threshold: int = 50
    daily_cooldown_seconds: int = 86400
    relief_cooldown_seconds: int = 259200

    def __post_init__(self) -> None:
        values = (
            self.welcome_grant,
            self.daily_bonus,
            self.relief_grant,
            self.relief_threshold,
            self.daily_cooldown_seconds,
            self.relief_cooldown_seconds,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise TypeError("economy values must be integers")
        if any(value < 0 for value in values):
            raise ValueError("economy values cannot be negative")


def validate_wallet_delta(balance: int, delta: int) -> int:
    """Return the next balance or reject a mutation below zero."""

    if isinstance(balance, bool) or not isinstance(balance, int) or balance < 0:
        raise ValueError("balance must be a non-negative integer")
    if isinstance(delta, bool) or not isinstance(delta, int):
        raise TypeError("delta must be an integer")

    next_balance = balance + delta
    if next_balance < 0:
        raise InsufficientBalanceError("wallet balance cannot become negative")
    return next_balance


def validate_bet(balance: int, amount: int, minimum: int, maximum: int) -> int:
    """Validate a whole-unit bet against balance and server-side limits."""

    if any(isinstance(value, bool) or not isinstance(value, int) for value in (amount, minimum, maximum)):
        raise TypeError("bet values must be integers")
    if minimum < 0 or maximum < minimum:
        raise ValueError("bet limits must be ordered and non-negative")
    if amount < minimum or amount > maximum:
        raise ValueError(f"bet must be between {minimum} and {maximum}")
    if isinstance(balance, bool) or not isinstance(balance, int) or balance < amount:
        raise InsufficientBalanceError("insufficient balance for bet")
    return amount
