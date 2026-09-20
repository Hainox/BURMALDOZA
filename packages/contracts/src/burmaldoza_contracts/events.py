from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: UUID
    room_id: UUID
    state_version: int = Field(ge=0)
    type: str = Field(min_length=1)
    ruleset_version: str = Field(min_length=1)
    server_time: datetime
    payload: dict[str, Any] = Field(default_factory=dict)
    animation_hint: str = Field(min_length=1)
