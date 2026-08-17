from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class RunResult(BaseModel):
    status: Literal[
        "success",
        "business_outcome",
        "recoverable_error",
        "failure",
    ]
    run_id: str
    outputs: dict[str, Any] = Field(default_factory=dict)
    code: str | None = None
    message: str | None = None
    step_id: str | None = None
    evidence: str | None = None
    recoveries: list[dict[str, Any]] = Field(default_factory=list)
