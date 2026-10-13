import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from burmaldoza_domain.games.slot_operations import (
    ROTATION_START,
    OperationOverride,
    select_operation,
)


def test_moscow_week_boundary_cycle_and_prelaunch():
    boundary = ROTATION_START + timedelta(days=7)
    assert select_operation(ROTATION_START - timedelta(days=1)).operation_id == "op1"
    assert select_operation(boundary - timedelta(microseconds=1)).operation_id == "op1"
    assert select_operation(boundary).operation_id == "op2"
    assert select_operation(boundary.astimezone(UTC)).operation_id == "op2"
    assert select_operation(ROTATION_START + timedelta(days=28)).operation_id == "op1"
    assert select_operation(ROTATION_START).changes_at == boundary
    assert select_operation(ROTATION_START).next_operation_id == "op2"


def test_event_interval_and_calendar_continue_under_override():
    start = ROTATION_START + timedelta(days=5)
    end = ROTATION_START + timedelta(days=8)
    event = OperationOverride("arena", start, end)
    before = select_operation(start - timedelta(seconds=1), event)
    assert (before.operation_id, before.next_operation_id, before.changes_at) == ("op1", "arena", start)
    during = select_operation(start, event)
    assert (during.operation_id, during.next_operation_id, during.changes_at) == ("arena", "op2", end)
    assert select_operation(end, event).operation_id == "op2"


def test_naive_time_and_invalid_overrides_are_rejected():
    with pytest.raises(ValueError):
        select_operation(datetime(2026, 10, 19, tzinfo=UTC).replace(tzinfo=None))
    for code, start, end in [
        ("op1", ROTATION_START, ROTATION_START + timedelta(days=1)),
        ("arena", ROTATION_START, ROTATION_START),
    ]:
        with pytest.raises(ValueError):
            OperationOverride(code, start, end)


def test_packaged_lineups_match_owner_approved_preview():
    import burmaldoza_domain.games.slot_operations as module

    root = Path(__file__).resolve().parents[3]
    script = (root / "assets/design/slot-r6/lineups.js").read_text(encoding="utf-8")
    preview = json.loads(script[script.index("{"):].strip().removesuffix(";"))
    packaged = json.loads(Path(module.__file__).with_suffix(".json").read_text(encoding="utf-8"))
    assert packaged == preview
