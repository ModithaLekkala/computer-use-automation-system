import re, uuid
from src.capabilities.compiler import compile_member_lookup
from src.observability.evidence import EvidenceRecorder

class DiscoveryAgent:
    def __init__(self, surface, planner, evidence_dir="evidence/discovery", max_steps=12):
        self.surface, self.planner, self.max_steps = surface, planner, max_steps
        self.evidence = EvidenceRecorder(evidence_dir)

    async def run(self, goal: str, target: str):
        m = re.search(r"\b(\d{4,})\b", goal)
        if not m: raise ValueError("Demo discovery expects a numeric member ID in the goal")
        member_id, run_id = m.group(1), str(uuid.uuid4())
        history, actions = [], []
        self.evidence.event("discovery_started", {"run_id":run_id,"goal":goal,"target":target})
        await self.surface.start(target)
        try:
            for n in range(1, self.max_steps+1):
                snapshot = await self.surface.snapshot()
                action = await self.planner.next_action(goal, snapshot, history)
                self.evidence.event("decision", {"run_id":run_id,"step":n,"action":action.model_dump()})
                if action.action == "done":
                    artifact = compile_member_lookup(goal, target, actions)
                    self.evidence.event("discovery_succeeded", {"run_id":run_id,"artifact":artifact.name})
                    return artifact
                if action.action == "escalate": raise RuntimeError(action.reason or action.description)
                value = member_id if action.value == "{{member_id}}" else action.value
                if action.action == "fill": await self.surface.fill(action.target, value)
                elif action.action == "click": await self.surface.click(action.target)
                elif action.action == "extract":
                    observed = await self.surface.extract(action.target)
                    self.evidence.event("extracted", {"run_id":run_id,"name":action.output_name,"value":observed})
                actions.append(action); history.append(action.model_dump())
            raise RuntimeError("Discovery exceeded max step budget")
        finally:
            await self.surface.close()
