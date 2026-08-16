from __future__ import annotations

from urllib.parse import urlparse

from src.agent.models import AgentAction
from src.capabilities.schema import (
    BusinessOutcome,
    CapabilityArtifact,
    CapabilityPolicy,
    CapabilityStep,
    Checkpoint,
    InputSpec,
    LocatorCandidate,
    LocatorKind,
    OutputSpec,
    RiskLevel,
    TargetRef,
)


def compile_member_lookup(
    goal: str,
    entry_url: str,
    actions: list[AgentAction],
) -> CapabilityArtifact:
    """
    Convert the successful LLM discovery run into a reusable,
    deterministic capability.

    Important:
    - Discovery-time member IDs must not be persisted.
    - Discovery-time output values must not become locators.
    - Replay must use stable semantic/structural targeting.
    """

    parsed = urlparse(entry_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    steps: list[CapabilityStep] = []
    outputs: dict[str, OutputSpec] = {}

    for action in actions:
        if action.action in {"done", "escalate"}:
            continue

        step_id = f"step_{len(steps) + 1}"

        target = action.target
        value = action.value
        description = action.description

        # ---------------------------------------------------------
        # MEMBER ID INPUT
        # ---------------------------------------------------------
        # Gemini may discover using the concrete value "10042".
        # The compiled capability must instead accept member_id
        # dynamically during every replay.
        if action.action == "fill":
            value = "{{member_id}}"

            description = "Enter the supplied member ID"

            target = TargetRef(
                description="Member ID input field",
                candidates=[
                    LocatorCandidate(
                        kind=LocatorKind.LABEL,
                        value="Member ID",
                    ),
                    LocatorCandidate(
                        kind=LocatorKind.CSS,
                        value="input[name='member_id']",
                    ),
                    LocatorCandidate(
                        kind=LocatorKind.CSS,
                        value="#legacy_mid",
                    ),
                ],
            )

        # ---------------------------------------------------------
        # SEARCH BUTTON
        # ---------------------------------------------------------
        if (
            action.action == "click"
            and (
                "search" in action.description.lower()
                or (
                    action.target
                    and "search" in action.target.description.lower()
                )
            )
        ):
            description = "Submit the member search"

            target = TargetRef(
                description="Search button",
                candidates=[
                    LocatorCandidate(
                        kind=LocatorKind.ROLE,
                        value="button",
                        name="Search",
                    ),
                    LocatorCandidate(
                        kind=LocatorKind.TEXT,
                        value="Search",
                    ),
                ],
            )

        # ---------------------------------------------------------
        # SAVINGS BALANCE OUTPUT
        # ---------------------------------------------------------
        # Gemini may produce a locator such as text="4281.52".
        # That would only work for the member used during discovery.
        #
        # Replace it with a stable locator for the balance field itself.
        if (
            action.action == "extract"
            and action.output_name == "savings_balance"
        ):
            description = "Extract the current savings balance"

            target = TargetRef(
                description="Savings balance value",
                candidates=[
                    LocatorCandidate(
                        kind=LocatorKind.CSS,
                        value="[data-field='savings-balance']",
                    ),
                    LocatorCandidate(
                        kind=LocatorKind.CSS,
                        value=".savings-balance",
                    ),
                ],
            )

        # ---------------------------------------------------------
        # OPTIONAL MEMBER NAME OUTPUT
        # ---------------------------------------------------------
        if (
            action.action == "extract"
            and action.output_name == "member_name"
        ):
            description = "Extract the member name"

            target = TargetRef(
                description="Member name",
                candidates=[
                    LocatorCandidate(
                        kind=LocatorKind.CSS,
                        value="[data-field='member-name']",
                    ),
                    LocatorCandidate(
                        kind=LocatorKind.CSS,
                        value=".member-name",
                    ),
                ],
            )

        step = CapabilityStep(
            id=step_id,
            action=action.action,
            description=description,
            target=target,
            value=value,
            output_name=action.output_name,
            timeout_ms=5000,
        )

        steps.append(step)

        # ---------------------------------------------------------
        # DECLARE OUTPUT CONTRACT
        # ---------------------------------------------------------
        if action.action == "extract" and action.output_name:
            outputs[action.output_name] = OutputSpec(
                type="string",
                description=(
                    "Current savings balance"
                    if action.output_name == "savings_balance"
                    else f"Extracted {action.output_name}"
                ),
                source_step_id=step_id,
            )

    # A successful discovery for this particular capability is not
    # acceptable unless the requested balance was actually extracted.
    if "savings_balance" not in outputs:
        raise RuntimeError(
            "Discovery cannot be compiled: "
            "the LLM did not extract savings_balance."
        )

    return CapabilityArtifact(
        schema_version="1.0",
        capability_version="1.0.0",

        name="lookup_member_balance",

        description=(
            "Look up a member by ID and return their current savings balance."
        ),

        app_id="legacybank-demo",

        entry_url=entry_url,

        allowed_origins=[
            origin,
        ],

        inputs={
            "member_id": InputSpec(
                type="string",
                description="Institution member identifier",
                required=True,
                sensitive=False,
            ),
        },

        outputs=outputs,

        steps=steps,

        checkpoint=Checkpoint(
            kind="visible_text",
            value="Member Profile",
        ),

        business_outcomes=[
            BusinessOutcome(
                code="MEMBER_NOT_FOUND",
                description=(
                    "No member exists for the supplied member ID."
                ),
                detector=Checkpoint(
                    kind="visible_text",
                    value="No member found",
                ),
            ),
        ],

        policy=CapabilityPolicy(
            risk=RiskLevel.READ_ONLY,
            allowed_actions=[
                "goto",
                "click",
                "fill",
                "extract",
                "wait",
            ],
            requires_confirmation=False,
        ),

        metadata={
            "source": "llm_discovery_compiled",
            "goal_template": (
                "Look up member {{member_id}} "
                "and read their current savings balance"
            ),
        },
    )