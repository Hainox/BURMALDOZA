"""Shared errors and validation primitives for pure game rules."""


class DomainError(ValueError):
    """Base error raised when a domain invariant is violated."""


class InsufficientBalanceError(DomainError):
    """Raised when an operation would make a wallet balance negative."""


class InvalidActionError(DomainError):
    """Raised when an action is not legal for the current game state."""


class StateVersionConflictError(DomainError):
    """Raised when a client action was based on an old confirmed state."""
