from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .common import GameType, RoomStatus


class ActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action_id: UUID
    expected_state_version: int = Field(ge=0)
    payload: dict[str, Any] = Field(default_factory=dict)


class RoomCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    game_type: GameType
    mode: str = Field(min_length=1, max_length=32)


class WebSocketAuthMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["auth"]
    init_data: str = Field(min_length=1)


class RoomSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    room_id: UUID
    game_type: GameType
    mode: str
    status: RoomStatus
    ruleset_version: str
    state_version: int = Field(ge=0)
    public_state: dict[str, Any] = Field(default_factory=dict)
