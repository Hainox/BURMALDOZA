from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .slot import SlotConfig


def _default_fixture_path() -> Path:
    return Path(__file__).resolve().parents[5] / "tests" / "fixtures" / "slot_skeleton.json"


def load_skeleton_config(path: str | Path | None = None) -> SlotConfig:
    fixture_path = Path(path) if path is not None else _default_fixture_path()
    raw: dict[str, Any] = json.loads(fixture_path.read_text(encoding="utf-8"))
    paytable = {
        (symbol, int(count)): int(multiplier)
        for symbol, payouts in raw["paytable"].items()
        for count, multiplier in payouts.items()
    }
    return SlotConfig(
        columns=int(raw["columns"]),
        rows=int(raw["rows"]),
        reel_strips=tuple(tuple(str(symbol) for symbol in strip) for strip in raw["reel_strips"]),
        paylines=tuple(tuple(int(row) for row in line) for line in raw["paylines"]),
        paytable=paytable,
        wild_symbol=raw.get("wild_symbol"),
        ruleset_version=str(raw["ruleset_version"]),
    )
