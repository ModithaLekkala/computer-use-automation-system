from urllib.parse import urlparse
from src.capabilities.schema import CapabilityArtifact, CapabilityStep, RiskLevel

class PolicyViolation(RuntimeError):
    pass

class PolicyEngine:
    def validate_origin(self, url: str, allowed_origins: list[str]) -> None:
        p = urlparse(url)
        origin = f"{p.scheme}://{p.netloc}"
        if origin not in allowed_origins:
            raise PolicyViolation(f"Origin {origin!r} is not allowlisted")

    def validate_step(self, artifact: CapabilityArtifact, step: CapabilityStep) -> None:
        if step.action not in artifact.policy.allowed_actions:
            raise PolicyViolation(f"Action {step.action!r} is not allowed")
        if artifact.policy.risk == RiskLevel.IRREVERSIBLE and artifact.policy.requires_confirmation:
            if step.action in {"click", "fill"}:
                raise PolicyViolation("Irreversible mutation requires explicit human confirmation")
