import asyncio, re, uuid
from typing import Any
from src.capabilities.schema import CapabilityArtifact, Checkpoint
from src.observability.evidence import EvidenceRecorder
from src.policy.guardrails import PolicyEngine, PolicyViolation
from src.replay.result import RunResult
from src.surfaces.base import SurfaceAdapter

PARAM_RE = re.compile(r"^\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}$")

class ReplayEngine:
    def __init__(self, surface: SurfaceAdapter, evidence_dir: str = "evidence/replay"):
        self.surface = surface
        self.policy = PolicyEngine()
        self.evidence = EvidenceRecorder(evidence_dir)

    def _bind(self, raw: str | None, inputs: dict[str, Any]) -> str | None:
        if raw is None: return None
        m = PARAM_RE.match(raw)
        if not m: return raw
        name = m.group(1)
        if name not in inputs: raise ValueError(f"Missing required capability input: {name}")
        return str(inputs[name])

    async def _checkpoint(self, cp: Checkpoint) -> bool:
        if cp.kind == "visible_text": return await self.surface.visible_text(cp.value)
        if cp.kind == "url_contains": return cp.value in self.surface.current_url
        if cp.kind == "element_visible" and cp.target:
            try:
                await self.surface.extract(cp.target, 1500)
                return True
            except Exception: return False
        return False

    async def run(self, artifact: CapabilityArtifact, inputs: dict[str, Any]) -> RunResult:
        run_id = str(uuid.uuid4())
        self.evidence.event("replay_started", {"run_id": run_id, "capability": artifact.name, "inputs": inputs})
        started = False
        try:
            self.policy.validate_origin(artifact.entry_url, artifact.allowed_origins)
            await self.surface.start(artifact.entry_url); started = True
            outputs = {}
            for step in artifact.steps:
                self.evidence.event("step_started", {"run_id": run_id, "step_id": step.id, "action": step.action})
                self.policy.validate_step(artifact, step)
                value = self._bind(step.value, inputs)
                if step.action == "goto": await self.surface.goto(value or artifact.entry_url)
                elif step.action == "click": await self.surface.click(step.target, step.timeout_ms)
                elif step.action == "fill": await self.surface.fill(step.target, value, step.timeout_ms)
                elif step.action == "extract":
                    outputs[step.output_name] = await self.surface.extract(step.target, step.timeout_ms)
                elif step.action == "wait": await asyncio.sleep(float(value or "0.5"))
                self.evidence.event("step_completed", {"run_id": run_id, "step_id": step.id})

                for outcome in artifact.business_outcomes:
                    if await self._checkpoint(outcome.detector):
                        shot = self.evidence.screenshot_path(f"{run_id}-{outcome.code}")
                        await self.surface.screenshot(shot)
                        result = RunResult(status="business_outcome", run_id=run_id, code=outcome.code, message=outcome.description, step_id=step.id, evidence=shot)
                        self.evidence.event("business_outcome", result.model_dump()); return result

            if not await self._checkpoint(artifact.checkpoint):
                shot = self.evidence.screenshot_path(f"{run_id}-checkpoint-failure")
                await self.surface.screenshot(shot)
                result = RunResult(status="failure", run_id=run_id, code="CHECKPOINT_FAILURE", message="Final checkpoint not satisfied", evidence=shot)
                self.evidence.event("replay_failed", result.model_dump()); return result

            result = RunResult(status="success", run_id=run_id, outputs=outputs)
            self.evidence.event("replay_succeeded", result.model_dump()); return result
        except PolicyViolation as e:
            result = RunResult(status="failure", run_id=run_id, code="POLICY_VIOLATION", message=str(e))
            self.evidence.event("replay_failed", result.model_dump()); return result
        except Exception as e:
            shot = None
            if started:
                try:
                    shot = self.evidence.screenshot_path(f"{run_id}-failure")
                    await self.surface.screenshot(shot)
                except Exception: shot = None
            result = RunResult(status="failure", run_id=run_id, code=type(e).__name__.upper(), message=str(e), evidence=shot)
            self.evidence.event("replay_failed", result.model_dump()); return result
        finally:
            if started: await self.surface.close()
