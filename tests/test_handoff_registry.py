from src.escalation.manager import (
    ControlOwner,
    Intervention,
    InterventionRegistry,
    RunState,
)


def test_handoff_state_transitions():
    registry = InterventionRegistry()
    registry.create(
        Intervention(
            run_id="run-1",
            goal_or_capability="lookup_member_balance",
            step_id="step_2",
            reason="Manual Review Required",
            screenshot="evidence/handoff/test.png",
        )
    )

    item = registry.take_control("run-1")
    assert item.owner == ControlOwner.HUMAN
    assert item.state == RunState.HUMAN_CONTROL

    item = registry.resume("run-1")
    assert item.owner == ControlOwner.AUTOMATION
    assert item.state == RunState.RESUMING
