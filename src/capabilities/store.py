from pathlib import Path
from .schema import CapabilityArtifact

def save_artifact(artifact: CapabilityArtifact, path: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")

def load_artifact(path: str) -> CapabilityArtifact:
    return CapabilityArtifact.model_validate_json(Path(path).read_text(encoding="utf-8"))
