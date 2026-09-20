from __future__ import annotations

import random
import secrets
from collections.abc import MutableSequence, Sequence
from typing import Protocol, TypeVar

T = TypeVar("T")


class RandomSource(Protocol):
    def randbelow(self, upper: int) -> int:
        """Return a value in the half-open interval [0, upper)."""

    def choice(self, sequence: Sequence[T]) -> T:
        """Return one item from a non-empty sequence."""

    def shuffle(self, values: MutableSequence[T]) -> None:
        """Shuffle a mutable sequence in place."""


class SystemRandomSource:
    """Production adapter backed by the operating system's CSPRNG."""

    def __init__(self) -> None:
        self._random = secrets.SystemRandom()

    def randbelow(self, upper: int) -> int:
        if upper <= 0:
            raise ValueError("upper must be positive")
        return self._random.randrange(upper)

    def choice(self, sequence: Sequence[T]) -> T:
        return self._random.choice(sequence)

    def shuffle(self, values: MutableSequence[T]) -> None:
        self._random.shuffle(values)


class SeededRandomSource:
    """Deterministic adapter for tests and offline Monte Carlo simulations."""

    def __init__(self, seed: int) -> None:
        self._random = random.Random(seed)

    def randbelow(self, upper: int) -> int:
        if upper <= 0:
            raise ValueError("upper must be positive")
        return self._random.randrange(upper)

    def choice(self, sequence: Sequence[T]) -> T:
        return self._random.choice(sequence)

    def shuffle(self, values: MutableSequence[T]) -> None:
        self._random.shuffle(values)
