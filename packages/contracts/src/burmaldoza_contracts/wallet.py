from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WalletSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: int = Field(gt=0)
    balance: int = Field(ge=0)
    currency_code: str = Field(min_length=1)
    version: int = Field(ge=0)


class LedgerEntryContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    operation_id: UUID
    amount_delta: int
    balance_after: int = Field(ge=0)
    reason: str = Field(min_length=1)
    reference_type: str = Field(min_length=1)
    reference_id: UUID | None = None
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
