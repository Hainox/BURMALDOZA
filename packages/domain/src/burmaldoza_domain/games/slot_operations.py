"""Cosmetic schedules only; symbol codes and payout rules are independent."""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

MOSCOW = timezone(timedelta(hours=3))
ROTATION_START = datetime(2026, 10, 19, tzinfo=MOSCOW)
_WEEK = timedelta(days=7)
_LINEUPS = json.loads(Path(__file__).with_suffix(".json").read_text(encoding="utf-8"))
_REGULAR = tuple(op["id"] for op in _LINEUPS["ops"] if op["kind"] == "season")
_EVENTS = frozenset(op["id"] for op in _LINEUPS["ops"] if op["kind"] == "event")
if (
    _REGULAR != ("op1", "op2", "op3", "op4")
    or _EVENTS != {"arena"}
    or _LINEUPS["wild"] != "Tachanka"
    or any(len(op["def"]) != 4 or len(op["atk"]) != 3 for op in _LINEUPS["ops"])
):
    raise ValueError("invalid approved slot operation lineups")


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("operation time must include a timezone")
    return value.astimezone(MOSCOW)


@dataclass(frozen=True, slots=True)
class OperationOverride:
    operation_id: str
    starts_at: datetime
    ends_at: datetime

    def __post_init__(self) -> None:
        if self.operation_id not in _EVENTS:
            raise ValueError("unknown event operation")
        if _aware(self.starts_at) >= _aware(self.ends_at):
            raise ValueError("event start must precede event end")


@dataclass(frozen=True, slots=True)
class OperationSchedule:
    operation_id: str
    next_operation_id: str
    changes_at: datetime


def _regular(now: datetime) -> OperationSchedule:
    weeks = max(0, (now - ROTATION_START) // _WEEK)
    return OperationSchedule(
        _REGULAR[weeks % 4],
        _REGULAR[(weeks + 1) % 4],
        ROTATION_START + (weeks + 1) * _WEEK,
    )


def select_operation(
    now: datetime, override: OperationOverride | None = None
) -> OperationSchedule:
    now = _aware(now)
    scheduled = _regular(now)
    if override is None:
        return scheduled
    start, end = _aware(override.starts_at), _aware(override.ends_at)
    if start <= now < end:
        return OperationSchedule(override.operation_id, _regular(end).operation_id, end)
    if now < start <= scheduled.changes_at:
        return OperationSchedule(scheduled.operation_id, override.operation_id, start)
    return scheduled
