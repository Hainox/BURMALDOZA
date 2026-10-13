from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict

OperationId = Literal["op1", "op2", "op3", "op4", "arena"]


class SlotOperationMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    operation_id: OperationId
    next_operation_id: OperationId
    operation_changes_at: AwareDatetime
