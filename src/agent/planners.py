import json, os
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
