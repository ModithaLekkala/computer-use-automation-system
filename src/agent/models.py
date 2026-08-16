from typing import Literal
from pydantic import BaseModel
from src.capabilities.schema import TargetRef

class AgentAction(BaseModel):
    action: Literal["click", "fill", "extract", "done", "escalate"]
    description: str
    target: TargetRef | None = None
    value: str | None = None
    output_name: str | None = None
    success: bool | None = None
    reason: str | None = None
