import pytest
from src.capabilities.store import load_artifact
from src.policy.guardrails import PolicyEngine, PolicyViolation
def test_allowlist_accepts_demo():
    a=load_artifact("artifacts/lookup_member_balance.json"); PolicyEngine().validate_origin(a.entry_url,a.allowed_origins)
def test_allowlist_rejects_other_origin():
    with pytest.raises(PolicyViolation): PolicyEngine().validate_origin("https://example.com",["http://127.0.0.1:8000"])
