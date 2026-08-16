from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field

class RiskLevel(str, Enum):
    READ_ONLY = "read_only"
    REVERSIBLE = "reversible"
    IRREVERSIBLE = "irreversible"

class LocatorKind(str, Enum):
    ROLE = "role"
    LABEL = "label"
    TEXT = "text"
    CSS = "css"

class LocatorCandidate(BaseModel):
    kind: LocatorKind
    value: str
    name: str | None = None
    exact: bool = True

class TargetRef(BaseModel):
    description: str
    candidates: list[LocatorCandidate] = Field(min_length=1)

class InputSpec(BaseModel):
    type: Literal["string", "integer", "number", "boolean"]
    description: str
    required: bool = True
    sensitive: bool = False

class OutputSpec(BaseModel):
    type: Literal["string", "integer", "number", "boolean"]
    description: str
    source_step_id: str

class Checkpoint(BaseModel):
    kind: Literal["visible_text", "url_contains", "element_visible"]
    value: str
    target: TargetRef | None = None

class CapabilityStep(BaseModel):
    id: str
    action: Literal["goto", "click", "fill", "extract", "wait"]
    description: str
    target: TargetRef | None = None
    value: str | None = None
    output_name: str | None = None
    timeout_ms: int = 5000

class BusinessOutcome(BaseModel):
    code: str
    description: str
    detector: Checkpoint

class CapabilityPolicy(BaseModel):
    risk: RiskLevel = RiskLevel.READ_ONLY
    allowed_actions: list[str]
    requires_confirmation: bool = False

class CapabilityArtifact(BaseModel):
    schema_version: str = "1.0"
    capability_version: str = "1.0.0"
    name: str
    description: str
    app_id: str
    entry_url: str
    allowed_origins: list[str]
    inputs: dict[str, InputSpec]
    outputs: dict[str, OutputSpec]
    steps: list[CapabilityStep]
    checkpoint: Checkpoint
    business_outcomes: list[BusinessOutcome] = []
    policy: CapabilityPolicy
    metadata: dict[str, Any] = {}
