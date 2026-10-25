from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

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
    buy_in: StrictInt | None = None
    action_id: UUID | None = None
    table_capacity: StrictInt | None = None

    @model_validator(mode="after")
    def validate_holdem_table(self) -> RoomCreateRequest:
        if self.game_type is GameType.HOLDEM:
            if self.mode not in {"bot", "pvp"}:
                raise ValueError("Hold'em mode must be bot or pvp")
            if self.buy_in not in (100, 500, 1000) or self.action_id is None:
                raise ValueError("Hold'em requires buy_in 100/500/1000 and action_id")
            if self.table_capacity is not None and (self.mode != "pvp" or self.table_capacity != 6):
                raise ValueError("table_capacity=6 requires Hold'em pvp")
        elif self.game_type is GameType.BLACKJACK and self.mode == "table":
            if self.action_id is None or self.buy_in is not None or self.table_capacity is not None:
                raise ValueError("Blackjack table requires action_id without buy_in or capacity")
        elif self.buy_in is not None or self.action_id is not None or self.table_capacity is not None:
            raise ValueError("buy_in and creation action_id are only accepted for Hold'em")
        return self


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


class HoldemOpponentProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    nickname: str = Field(min_length=1, max_length=256)
    avatar_path: str


class RoomJoinRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    action_id: UUID
