from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LeaderboardEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rank: int = Field(ge=1, le=15)
    nickname: str = Field(min_length=1)
    net_result: int


class LeaderboardOwnPlace(BaseModel):
    """The caller's own place when they played this week but are outside the top 15."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rank: int = Field(ge=16)
    nickname: str = Field(min_length=1)
    net_result: int


class LeaderboardSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    week_start: datetime
    week_end: datetime
    entries: list[LeaderboardEntry] = Field(max_length=15)
    me: LeaderboardOwnPlace | None = None
