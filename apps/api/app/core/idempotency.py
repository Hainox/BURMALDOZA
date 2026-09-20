from __future__ import annotations

from uuid import UUID


class InvalidIdempotencyKey(ValueError):
    """Raised when a mutating request does not carry a valid request UUID."""


def parse_idempotency_key(value: str | None) -> UUID:
    if not value:
        raise InvalidIdempotencyKey("X-Request-ID is required")
    try:
        key = UUID(value)
    except (AttributeError, ValueError) as error:
        raise InvalidIdempotencyKey("X-Request-ID must be a UUID") from error
    if key.int == 0:
        raise InvalidIdempotencyKey("X-Request-ID must not be empty")
    return key
