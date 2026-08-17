from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from threading import Condition, Lock
from typing import Optional


class ControlOwner(str, Enum):
    AUTOMATION = "AUTOMATION"
    HUMAN = "HUMAN"


class RunState(str, Enum):
    RUNNING = "RUNNING"
    PAUSED_FOR_HUMAN = "PAUSED_FOR_HUMAN"
    HUMAN_CONTROL = "HUMAN_CONTROL"
    RESUMING = "RESUMING"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"


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
    """In-process control-transfer registry.

    The browser remains owned by the running automation process. A human can
    claim the already-open headed Chromium window, perform the required manual
    action, then signal resume through the operator endpoint.
    """

    def __init__(self):
        self._items: dict[str, Intervention] = {}
        self._lock = Lock()
        self._condition = Condition(self._lock)

    def create(self, intervention: Intervention) -> Intervention:
        with self._condition:
            self._items[intervention.run_id] = intervention
            self._condition.notify_all()
            return intervention

    def get(self, run_id: str) -> Optional[Intervention]:
        with self._lock:
            return self._items.get(run_id)

    def all(self) -> list[dict]:
        with self._lock:
            return [asdict(v) for v in self._items.values()]

    def take_control(self, run_id: str) -> Intervention:
        with self._condition:
            item = self._items[run_id]
            item.owner = ControlOwner.HUMAN
            item.state = RunState.HUMAN_CONTROL
            self._condition.notify_all()
            return item

    def resume(self, run_id: str) -> Intervention:
        with self._condition:
            item = self._items[run_id]
            item.owner = ControlOwner.AUTOMATION
            item.state = RunState.RESUMING
            self._condition.notify_all()
            return item

    def abort(self, run_id: str) -> Intervention:
        with self._condition:
            item = self._items[run_id]
            item.owner = ControlOwner.AUTOMATION
            item.state = RunState.ABORTED
            self._condition.notify_all()
            return item

    def complete(self, run_id: str) -> None:
        with self._condition:
            item = self._items.get(run_id)
            if item:
                item.state = RunState.COMPLETED
                item.owner = ControlOwner.AUTOMATION
            self._condition.notify_all()


registry = InterventionRegistry()
