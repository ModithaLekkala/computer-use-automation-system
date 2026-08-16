import re
from typing import Any

SENSITIVE_KEYS = {"password", "token", "secret", "authorization", "cookie", "ssn"}
SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
BEARER = re.compile(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*")

def redact_text(text: str) -> str:
    return BEARER.sub("[REDACTED]", SSN.sub("[REDACTED]", text))

def redact(value: Any) -> Any:
    if isinstance(value, str): return redact_text(value)
    if isinstance(value, list): return [redact(v) for v in value]
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            out[k] = "[REDACTED]" if any(x in k.lower() for x in SENSITIVE_KEYS) else redact(v)
        return out
    return value
