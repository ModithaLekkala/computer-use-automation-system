from typing import Any, Literal
from pydantic import BaseModel

class RunResult(BaseModel):
    status: Literal["success", "business_outcome", "recoverable_error", "failure"]
    run_id: str
    outputs: dict[str, Any] = {}
    code: str | None = None
    message: str | None = None
    step_id: str | None = None
    evidence: str | None = None
