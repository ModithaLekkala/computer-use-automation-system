from urllib.parse import urlparse
from src.capabilities.schema import *

def compile_member_lookup(goal, entry_url, actions):
    p = urlparse(entry_url); origin = f"{p.scheme}://{p.netloc}"
    steps, outputs = [], {}
    for i, a in enumerate(actions, 1):
        if a.action in {"done", "escalate"}: continue
        sid = f"step_{i}"
        steps.append(CapabilityStep(id=sid, action=a.action, description=a.description, target=a.target, value=a.value, output_name=a.output_name))
        if a.action == "extract" and a.output_name:
            outputs[a.output_name] = OutputSpec(type="string", description=f"Extracted {a.output_name}", source_step_id=sid)
    return CapabilityArtifact(name="lookup_member_balance", description="Look up a member by ID and return savings balance", app_id="legacybank-demo", entry_url=entry_url, allowed_origins=[origin], inputs={"member_id": InputSpec(type="string", description="Institution member identifier")}, outputs=outputs, steps=steps, checkpoint=Checkpoint(kind="visible_text", value="Member Profile"), business_outcomes=[BusinessOutcome(code="MEMBER_NOT_FOUND", description="No member exists for the supplied ID", detector=Checkpoint(kind="visible_text", value="No member found"))], policy=CapabilityPolicy(risk=RiskLevel.READ_ONLY, allowed_actions=["goto","click","fill","extract","wait"]), metadata={"source":"discovery","goal_template":"Look up member {{member_id}} and read their current savings balance"})
