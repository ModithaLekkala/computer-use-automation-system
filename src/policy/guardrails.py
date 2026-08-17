from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from src.capabilities.schema import CapabilityArtifact, CapabilityStep, RiskLevel


class PolicyViolation(RuntimeError):
    pass


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str


def origin_of(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


class PolicyEngine:
    DISCOVERY_ALLOWED_ACTIONS = {"click", "fill", "extract", "done", "escalate"}

    def validate_origin(self, url: str, allowed_origins: list[str]) -> None:
        origin = origin_of(url)
        if origin not in allowed_origins:
            raise PolicyViolation(f"Origin {origin!r} is not allowlisted.")

    def validate_discovery_action(self, action_type: str) -> None:
        if action_type not in self.DISCOVERY_ALLOWED_ACTIONS:
            raise PolicyViolation(
                f"Discovery action {action_type!r} is not allowlisted."
            )

    def validate_step(self, artifact: CapabilityArtifact, step: CapabilityStep) -> None:
        if step.action not in artifact.policy.allowed_actions:
            raise PolicyViolation(
                f"Action {step.action!r} is not allowed by the capability policy."
            )

        if (
            artifact.policy.risk == RiskLevel.IRREVERSIBLE
            and artifact.policy.requires_confirmation
            and step.action in {"click", "fill"}
        ):
            raise PolicyViolation(
                "Irreversible capability requires explicit human confirmation."
            )
