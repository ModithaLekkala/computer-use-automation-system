import json, os
from google import genai
from google.genai import types
from abc import ABC, abstractmethod
from dotenv import load_dotenv
from openai import AsyncOpenAI
from src.agent.models import AgentAction
from src.capabilities.schema import LocatorCandidate, LocatorKind, TargetRef
load_dotenv()

class Planner(ABC):
    @abstractmethod
    async def next_action(self, goal: str, snapshot: dict, history: list[dict]) -> AgentAction: ...

class MockPlanner(Planner):
    def __init__(self): self.state = 0
    async def next_action(self, goal, snapshot, history):
        self.state += 1
        if self.state == 1:
            return AgentAction(action="fill", description="Enter member ID", target=TargetRef(description="Member ID field", candidates=[LocatorCandidate(kind=LocatorKind.LABEL, value="Member ID"), LocatorCandidate(kind=LocatorKind.CSS, value="input[name='member_id']")]), value="{{member_id}}")
        if self.state == 2:
            return AgentAction(action="click", description="Submit search", target=TargetRef(description="Search button", candidates=[LocatorCandidate(kind=LocatorKind.ROLE, value="button", name="Search"), LocatorCandidate(kind=LocatorKind.TEXT, value="Search")]))
        if self.state == 3:
            return AgentAction(action="extract", description="Read member name", target=TargetRef(description="Member name", candidates=[LocatorCandidate(kind=LocatorKind.CSS, value="[data-field='member-name']")]), output_name="member_name")
        if self.state == 4:
            return AgentAction(action="extract", description="Read savings balance", target=TargetRef(description="Savings balance", candidates=[LocatorCandidate(kind=LocatorKind.CSS, value="[data-field='savings-balance']")]), output_name="savings_balance")
        return AgentAction(action="done", description="Goal complete", success=True)

class OpenAIPlanner(Planner):
    def __init__(self, model: str | None = None):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    async def next_action(self, goal, snapshot, history):
        schema = AgentAction.model_json_schema()
        prompt = f"""You control a real UI through a constrained action interface.
GOAL:
{goal}
CURRENT UI SNAPSHOT:
{json.dumps(snapshot)}
PRIOR ACTIONS:
{json.dumps(history[-8:])}
Return exactly one next action. Prefer role/label/text locators over CSS. Do not invent controls. Use parameter templates like {{{{member_id}}}} for reusable goal values. If complete return done. If unsafe or impossible return escalate."""
        response = await self.client.responses.create(model=self.model, input=prompt, text={"format": {"type": "json_schema", "name": "agent_action", "schema": schema, "strict": True}})
        return AgentAction.model_validate_json(response.output_text)



class GeminiPlanner(Planner):
    def __init__(self, model: str | None = None):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Add it to your .env file."
            )

        self.client = genai.Client(api_key=api_key)
        self.model = model or os.getenv(
            "GEMINI_MODEL",
            "gemini-2.5-flash",
        )

    async def next_action(
        self,
        goal: str,
        snapshot: dict,
        history: list[dict],
    ) -> AgentAction:

        prompt = f"""
You are controlling a real user interface through a constrained automation system.

GOAL:
{goal}

CURRENT UI SNAPSHOT:
{json.dumps(snapshot, ensure_ascii=False)}

PRIOR ACTIONS:
{json.dumps(history[-8:], ensure_ascii=False)}

Choose exactly ONE next action.

Allowed actions:
- click
- fill
- extract
- done
- escalate

Rules:

1. Choose exactly ONE action for the current UI state.

2. Carefully inspect CURRENT UI SNAPSHOT before choosing an action.

3. Input controls include a "value" property. Use it to determine whether
   required task data has already been entered.

4. Before clicking Search, Submit, Continue, Save, or another form-submission
   control, verify from the CURRENT UI SNAPSHOT that every task-relevant input
   contains the expected value.

5. Prefer semantic locators in this order:
   - label
   - role + accessible name
   - visible text
   - CSS only when necessary

6. Never invent a control or locator that is not supported by the current UI
   snapshot.

7. Use PRIOR ACTIONS to understand what has already been attempted, but trust
   CURRENT UI SNAPSHOT for the present state.

8. Do not repeatedly perform an action simply because it appears in PRIOR
   ACTIONS. Decide from the current state whether it is still necessary.

9. For reusable values supplied by the user's goal, use a template parameter
   such as {{member_id}} instead of hard-coding the concrete value whenever
   possible.

10. Return action="done" only when CURRENT UI SNAPSHOT contains evidence that
    the user's requested goal has actually been achieved.

11. If the UI displays a validation or runtime error, determine whether a safe
    corrective action is available before escalating.

12. Return action="escalate" when:
    - the UI state cannot be safely understood,
    - no permitted recovery action exists,
    - an irreversible/risky decision requires a human,
    - or repeated safe attempts have failed.

13. Return only one structured action matching the required AgentAction schema.
14. The goal may contain both navigation/action requirements and information
    extraction requirements. Do not return action="done" merely because the
    destination page has been reached.

15. Before returning action="done", verify that every piece of information
    requested by the goal has been explicitly extracted through an
    action="extract" step.

16. For this task, reaching the member profile is NOT sufficient. If the goal
    asks for the current savings balance, you must locate and extract that
    balance before declaring success.

17. When a value originates from the user's goal and should vary between
    invocations, NEVER hard-code the concrete discovery value into the reusable
    action. Use a template parameter such as {{{{member_id}}}}.
"""

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AgentAction,
                temperature=0,
            ),
        )

        return AgentAction.model_validate_json(response.text)
