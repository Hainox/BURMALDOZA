from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .slot import SlotConfig

SLOT_RULESET_VERSIONS = ("slot-skeleton-1", "slot-siege-1", "slot-siege-2")
# Siege-версии с ротацией операций; slot-siege-2 — 9 линий (#91).
SIEGE_RULESET_VERSIONS = frozenset({"slot-siege-1", "slot-siege-2"})
_RULESET_FILES = {
    "slot-skeleton-1": "slot_skeleton.json",
    "slot-siege-1": "slot_siege.json",
    "slot-siege-2": "slot_siege_2.json",
}


def load_slot_config(version: str = "slot-siege-2") -> SlotConfig:
    """Load an explicitly registered ruleset; versions are never filesystem paths."""
    try:
        filename = _RULESET_FILES[version]
    except KeyError:
        raise ValueError(f"unknown slot ruleset: {version}") from None
    config = load_skeleton_config(Path(__file__).with_name(filename))
    if config.ruleset_version != version:
        raise ValueError("slot ruleset file version does not match registry")
    return config


def _default_ruleset_path() -> Path:
    # Shipped inside the package so the API image needs no extra mount.
    return Path(__file__).with_name("slot_skeleton.json")


def load_skeleton_config(path: str | Path | None = None) -> SlotConfig:
    fixture_path = Path(path) if path is not None else _default_ruleset_path()
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
