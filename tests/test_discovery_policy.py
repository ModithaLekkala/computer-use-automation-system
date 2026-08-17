import pytest

from src.policy.guardrails import PolicyEngine, PolicyViolation


def test_discovery_action_allowlist_accepts_safe_actions():
    policy = PolicyEngine()
    for action in ("click", "fill", "extract", "done", "escalate"):
        policy.validate_discovery_action(action)


def test_discovery_action_allowlist_rejects_unknown_action():
    with pytest.raises(PolicyViolation):
        PolicyEngine().validate_discovery_action("shell")
