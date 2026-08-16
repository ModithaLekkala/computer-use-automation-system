import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from src.policy.redaction import redact

class EvidenceRecorder:
    def __init__(self, directory: str):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / "screenshots").mkdir(exist_ok=True)
        self.log_path = self.directory / "run.jsonl"

    def event(self, event_type: str, payload: dict[str, Any]) -> None:
        item = {"ts": datetime.now(timezone.utc).isoformat(), "event": event_type, **redact(payload)}
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    def screenshot_path(self, name: str) -> str:
        safe = "".join(c for c in name if c.isalnum() or c in "-_")
        return str(self.directory / "screenshots" / f"{safe}.png")
