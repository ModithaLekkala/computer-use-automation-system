from __future__ import annotations

import re
import uuid
from urllib.parse import urlparse

from src.agent.models import AgentAction
from src.agent.planners import Planner
from src.capabilities.compiler import compile_member_lookup
from src.capabilities.schema import CapabilityArtifact
from src.observability.evidence import EvidenceRecorder
from src.policy.guardrails import PolicyEngine
from src.surfaces.base import SurfaceAdapter


def extract_member_id(goal: str) -> str:
    match = re.search(r"\b(\d{4,})\b", goal)
    if not match:
        raise ValueError("Demo discovery expects a numeric member ID in the goal.")
    return match.group(1)


def entry_origin(target: str) -> str:
    parsed = urlparse(target)
    return f"{parsed.scheme}://{parsed.netloc}"


class DiscoveryAgent:
    def __init__(
        self,
        surface: SurfaceAdapter,
        planner: Planner,
        evidence_dir: str = "evidence/discovery",
        max_steps: int = 12,
    ):
        self.surface = surface
        self.planner = planner
        self.policy = PolicyEngine()
        self.evidence = EvidenceRecorder(evidence_dir)
        self.max_steps = max_steps

    async def run(self, goal: str, target: str) -> CapabilityArtifact:
        run_id = str(uuid.uuid4())
        member_id = extract_member_id(goal)
        allowed_origins = [entry_origin(target)]
        history: list[dict] = []
        successful_actions: list[AgentAction] = []

        # Safety applies before the model touches the UI.
        self.policy.validate_origin(target, allowed_origins)

        self.evidence.event(
            "discovery_started",
            {"run_id": run_id, "goal": goal, "target": target},
        )

        await self.surface.start(target)
        try:
            for step_num in range(1, self.max_steps + 1):
                # Revalidate after every preceding action/navigation.
                self.policy.validate_origin(self.surface.current_url, allowed_origins)

                snapshot = await self.surface.snapshot()
                self.evidence.event(
                    "observation",
                    {
                        "run_id": run_id,
                        "step": step_num,
                        "url": snapshot.get("url"),
                        "title": snapshot.get("title"),
                    },
                )

                if "No member found" in snapshot.get("text", ""):
                    self.evidence.event(
                        "discovery_business_outcome",
                        {"run_id": run_id, "code": "MEMBER_NOT_FOUND"},
                    )
                    raise RuntimeError(
                        "Discovery input produced MEMBER_NOT_FOUND; use a valid demo member."
                    )

                action = await self.planner.next_action(goal, snapshot, history)

                # The model proposes; policy decides whether it may execute.
                self.policy.validate_discovery_action(action.action)

                self.evidence.event(
                    "decision",
                    {
                        "run_id": run_id,
                        "step": step_num,
                        "action": action.model_dump(),
                    },
                )

                if action.action == "done":
                    if not action.success:
                        raise RuntimeError("Planner stopped without declaring success.")
                    artifact = compile_member_lookup(goal, target, successful_actions)
                    self.evidence.event(
                        "discovery_succeeded",
                        {"run_id": run_id, "artifact": artifact.name},
                    )
                    return artifact

                if action.action == "escalate":
                    shot = self.evidence.screenshot_path(f"{run_id}-escalation")
                    await self.surface.screenshot(shot)
                    raise RuntimeError(
                        f"Human escalation requested: {action.reason or action.description}"
                    )

                exec_value = action.value
                if exec_value == "{{member_id}}":
                    exec_value = member_id

                if action.action == "click":
                    assert action.target
                    await self.surface.click(action.target)
                elif action.action == "fill":
                    assert action.target and exec_value is not None
                    await self.surface.fill(action.target, exec_value)
                elif action.action == "extract":
                    assert action.target
                    observed = await self.surface.extract(action.target)
                    self.evidence.event(
                        "extracted",
                        {
                            "run_id": run_id,
                            "name": action.output_name,
                            "value": observed,
                        },
                    )
                else:
                    raise RuntimeError(f"Unsupported discovery action: {action.action}")

                # Prevent a model action from escaping the allowed origin.
                self.policy.validate_origin(self.surface.current_url, allowed_origins)

                successful_actions.append(action)
                history.append(action.model_dump())

            shot = self.evidence.screenshot_path(f"{run_id}-max-steps")
            await self.surface.screenshot(shot)
            raise RuntimeError(
                "Discovery exceeded max step budget and should escalate."
            )
        finally:
            await self.surface.close()
