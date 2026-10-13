import asyncio
from types import SimpleNamespace

import pytest
from app import main


class _DriverError(Exception):
    """Stands in for driver errors such as asyncpg InvalidPasswordError (not SQLAlchemyError)."""


def _failing_session_factory():
    raise _DriverError("password authentication failed")


@pytest.mark.asyncio
async def test_holdem_timer_survives_driver_errors_outside_sqlalchemy(monkeypatch) -> None:
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)
        if len(sleeps) == 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(main.asyncio, "sleep", fake_sleep)
    application = SimpleNamespace(
        state=SimpleNamespace(session_factory=_failing_session_factory, event_bus=None)
    )

    with pytest.raises(asyncio.CancelledError):
        await main._holdem_timer(application)

    # Two ticks ran: the first failure was logged and backed off instead of killing the loop.
    assert sleeps == [5, 5]
