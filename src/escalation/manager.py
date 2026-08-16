from dataclasses import dataclass, asdict
from enum import Enum
from threading import Lock

class ControlOwner(str, Enum): AUTOMATION="AUTOMATION"; HUMAN="HUMAN"
class RunState(str, Enum): RUNNING="RUNNING"; PAUSED_FOR_HUMAN="PAUSED_FOR_HUMAN"; HUMAN_CONTROL="HUMAN_CONTROL"; RESUMING="RESUMING"; COMPLETED="COMPLETED"; ABORTED="ABORTED"
@dataclass
class Intervention:
    run_id: str
    goal_or_capability: str
    step_id: str | None
    reason: str
    screenshot: str | None
    state: RunState = RunState.PAUSED_FOR_HUMAN
    owner: ControlOwner = ControlOwner.AUTOMATION
class InterventionRegistry:
    def __init__(self): self._items={}; self._lock=Lock()
    def create(self, i): self._items[i.run_id]=i; return i
    def get(self, rid): return self._items.get(rid)
    def all(self): return [asdict(v) for v in self._items.values()]
    def take_control(self, rid):
        i=self._items[rid]; i.owner=ControlOwner.HUMAN; i.state=RunState.HUMAN_CONTROL; return i
    def resume(self, rid):
        i=self._items[rid]; i.owner=ControlOwner.AUTOMATION; i.state=RunState.RESUMING; return i
registry=InterventionRegistry()
