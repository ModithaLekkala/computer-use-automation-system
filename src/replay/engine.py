from __future__ import annotations

import asyncio
import re
import uuid
from typing import Any

from src.capabilities.schema import CapabilityArtifact, Checkpoint
from src.escalation.manager import (
    ControlOwner,
    Intervention,
    RunState,
    registry,
)
from src.escalation.server import OperatorServer
from src.observability.evidence import EvidenceRecorder
from src.policy.guardrails import PolicyEngine, PolicyViolation
from src.replay.result import RunResult
from src.surfaces.base import SurfaceAdapter

PARAM_RE = re.compile(r"^\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}$")


class ReplayEngine:
    MAX_RECOVERY_ATTEMPTS = 1

    def __init__(
        self,
        surface: SurfaceAdapter,
        evidence_dir: str = "evidence/replay",
        handoff_timeout_seconds: int = 300,
    ):
        self.surface = surface
        self.policy = PolicyEngine()
        self.evidence = EvidenceRecorder(evidence_dir)
        self.handoff_timeout_seconds = handoff_timeout_seconds

    def _bind(self, raw: str | None, inputs: dict[str, Any]) -> str | None:
        if raw is None:
            return None
        match = PARAM_RE.match(raw)
        if not match:
            return raw
        name = match.group(1)
        if name not in inputs:
            raise ValueError(f"Missing required capability input: {name}")
        return str(inputs[name])

    async def _checkpoint(self, cp: Checkpoint) -> bool:
        if cp.kind == "visible_text":
            return await self.surface.visible_text(cp.value)
        if cp.kind == "url_contains":
            return cp.value in self.surface.current_url
        if cp.kind == "element_visible":
            if not cp.target:
                return False
            try:
                await self.surface.extract(cp.target, timeout_ms=1500)
                return True
            except Exception:
                return False
        return False

    async def _recover_transient(
        self,
        run_id: str,
        step_id: str,
        recoveries: list[dict[str, Any]],
    ) -> bool:
        """One bounded known recovery: click Retry on Temporary Service Delay."""
        if not await self.surface.visible_text("Temporary Service Delay", timeout_ms=500):
            return False

        from src.capabilities.schema import (
            LocatorCandidate,
            LocatorKind,
            TargetRef,
        )

        recovery = {
            "code": "TRANSIENT_LOAD",
            "attempt": 1,
            "step_id": step_id,
        }
        recoveries.append(recovery)
        self.evidence.event(
            "recoverable_condition",
            {"run_id": run_id, **recovery},
        )

        retry_target = TargetRef(
            description="Retry button",
            candidates=[
                LocatorCandidate(
                    kind=LocatorKind.ROLE,
                    value="button",
                    name="Retry",
                ),
                LocatorCandidate(
                    kind=LocatorKind.TEXT,
                    value="Retry",
                ),
            ],
        )
        await self.surface.click(retry_target)
        self.evidence.event(
            "recovery_succeeded",
            {
                "run_id": run_id,
                "code": "TRANSIENT_LOAD",
                "attempt": 1,
            },
        )
        return True

    async def _human_handoff(
        self,
        run_id: str,
        capability_name: str,
        step_id: str,
    ) -> bool:
        """Pause while a human controls the SAME headed browser session.

        The browser stays open in this process. The embedded operator server uses
        the same in-memory registry. The human clicks Take Control in the operator
        page, operates the already-open Chromium window, and clicks Resume.
        """
        if not await self.surface.visible_text("Manual Review Required", timeout_ms=500):
            return False

        shot = self.evidence.screenshot_path(f"{run_id}-handoff")
        await self.surface.screenshot(shot)

        intervention = registry.create(
            Intervention(
                run_id=run_id,
                goal_or_capability=capability_name,
                step_id=step_id,
                reason="Manual Review Required",
                screenshot=shot,
            )
        )

        self.evidence.event(
            "automation_paused",
            {
                "run_id": run_id,
                "step_id": step_id,
                "reason": intervention.reason,
                "screenshot": shot,
                "operator_url": "http://127.0.0.1:8001",
            },
        )

        elapsed = 0.0
        saw_human_control = False

        while elapsed < self.handoff_timeout_seconds:
            item = registry.get(run_id)
            if item:
                if item.state == RunState.HUMAN_CONTROL and not saw_human_control:
                    saw_human_control = True
                    self.evidence.event(
                        "human_control",
                        {"run_id": run_id, "step_id": step_id},
                    )
                if item.state == RunState.RESUMING:
                    self.evidence.event(
                        "automation_resumed",
                        {"run_id": run_id, "step_id": step_id},
                    )
                    return True
                if item.state == RunState.ABORTED:
                    raise RuntimeError("Human operator aborted the run.")
            await asyncio.sleep(0.25)
            elapsed += 0.25

        raise RuntimeError(
            "Human intervention timed out before control was returned to automation."
        )

    async def run(
        self,
        artifact: CapabilityArtifact,
        inputs: dict[str, Any],
        enable_operator: bool = True,
    ) -> RunResult:
        run_id = str(uuid.uuid4())
        recoveries: list[dict[str, Any]] = []
        operator_server = OperatorServer() if enable_operator else None

        self.evidence.event(
            "replay_started",
            {
                "run_id": run_id,
                "capability": artifact.name,
                "inputs": inputs,
            },
        )

        try:
            self.policy.validate_origin(artifact.entry_url, artifact.allowed_origins)
            await self.surface.start(artifact.entry_url)

            if operator_server:
                operator_server.start()

            outputs: dict[str, Any] = {}

            for step in artifact.steps:
                self.policy.validate_origin(
                    self.surface.current_url,
                    artifact.allowed_origins,
                )

                self.evidence.event(
                    "step_started",
                    {
                        "run_id": run_id,
                        "step_id": step.id,
                        "action": step.action,
                        "description": step.description,
                    },
                )

                for outcome in artifact.business_outcomes:
                    if await self._checkpoint(outcome.detector):
                        shot = self.evidence.screenshot_path(
                            f"{run_id}-{outcome.code}"
                        )
                        await self.surface.screenshot(shot)
                        result = RunResult(
                            status="business_outcome",
                            run_id=run_id,
                            code=outcome.code,
                            message=outcome.description,
                            step_id=step.id,
                            evidence=shot,
                            recoveries=recoveries,
                        )
                        self.evidence.event("business_outcome", result.model_dump())
                        return result

                # Known runtime conditions are handled deliberately before the
                # next recorded step is executed.
                if await self._human_handoff(
                    run_id, artifact.name, step.id
                ):
                    self.policy.validate_origin(
                        self.surface.current_url,
                        artifact.allowed_origins,
                    )

                if await self._recover_transient(
                    run_id, step.id, recoveries
                ):
                    self.policy.validate_origin(
                        self.surface.current_url,
                        artifact.allowed_origins,
                    )

                self.policy.validate_step(artifact, step)
                value = self._bind(step.value, inputs)

                if step.action == "goto":
                    await self.surface.goto(value or artifact.entry_url)
                elif step.action == "click":
                    assert step.target
                    await self.surface.click(step.target, step.timeout_ms)
                elif step.action == "fill":
                    assert step.target and value is not None
                    await self.surface.fill(step.target, value, step.timeout_ms)
                elif step.action == "extract":
                    assert step.target and step.output_name
                    outputs[step.output_name] = await self.surface.extract(
                        step.target, step.timeout_ms
                    )
                elif step.action == "wait":
                    await asyncio.sleep(float(value or "0.5"))
                else:
                    raise RuntimeError(f"Unsupported step action: {step.action}")

                self.policy.validate_origin(
                    self.surface.current_url,
                    artifact.allowed_origins,
                )

                self.evidence.event(
                    "step_completed",
                    {"run_id": run_id, "step_id": step.id},
                )

            # A condition can appear after the last recorded step (for example,
            # immediately after Search), so process it before final outputs/checkpoint.
            if await self._human_handoff(
                run_id, artifact.name, artifact.steps[-1].id if artifact.steps else "final"
            ):
                pass

            if await self._recover_transient(
                run_id,
                artifact.steps[-1].id if artifact.steps else "final",
                recoveries,
            ):
                pass

            for outcome in artifact.business_outcomes:
                if await self._checkpoint(outcome.detector):
                    shot = self.evidence.screenshot_path(
                        f"{run_id}-{outcome.code}"
                    )
                    await self.surface.screenshot(shot)
                    result = RunResult(
                        status="business_outcome",
                        run_id=run_id,
                        code=outcome.code,
                        message=outcome.description,
                        evidence=shot,
                        recoveries=recoveries,
                    )
                    self.evidence.event("business_outcome", result.model_dump())
                    return result

            # If recovery/handoff occurred after Search but before Extract,
            # execute any extraction steps whose output has not yet been produced.
            for step in artifact.steps:
                if step.action == "extract" and step.output_name not in outputs:
                    self.policy.validate_step(artifact, step)
                    assert step.target and step.output_name
                    outputs[step.output_name] = await self.surface.extract(
                        step.target, step.timeout_ms
                    )

            if not await self._checkpoint(artifact.checkpoint):
                shot = self.evidence.screenshot_path(
                    f"{run_id}-checkpoint-failure"
                )
                await self.surface.screenshot(shot)
                result = RunResult(
                    status="failure",
                    run_id=run_id,
                    code="CHECKPOINT_FAILURE",
                    message=(
                        "Replay completed steps but final checkpoint "
                        "was not satisfied."
                    ),
                    evidence=shot,
                    recoveries=recoveries,
                )
                self.evidence.event("replay_failed", result.model_dump())
                return result

            registry.complete(run_id)
            result = RunResult(
                status="success",
                run_id=run_id,
                outputs=outputs,
                recoveries=recoveries,
            )
            self.evidence.event("replay_succeeded", result.model_dump())
            return result

        except PolicyViolation as exc:
            result = RunResult(
                status="failure",
                run_id=run_id,
                code="POLICY_VIOLATION",
                message=str(exc),
                recoveries=recoveries,
            )
            self.evidence.event("replay_failed", result.model_dump())
            return result

        except Exception as exc:
            shot = self.evidence.screenshot_path(f"{run_id}-failure")
            try:
                await self.surface.screenshot(shot)
            except Exception:
                shot = None
            result = RunResult(
                status="failure",
                run_id=run_id,
                code=type(exc).__name__.upper(),
                message=str(exc),
                evidence=shot,
                recoveries=recoveries,
            )
            self.evidence.event("replay_failed", result.model_dump())
            return result

        finally:
            if operator_server:
                operator_server.stop()
            await self.surface.close()
