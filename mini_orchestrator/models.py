from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List
import json
import uuid

from .model_defaults import DEFAULT_COORDINATOR_MODEL


@dataclass
class TaskAction:
    action_id: str
    step: int
    description: str
    tool: str
    args: Dict[str, Any]
    model: str


@dataclass
class StateEvent:
    stage: str
    status: str
    message: str
    attempt: int = 0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskState:
    request_id: str
    goal: str
    state: str
    next_action: str
    model: str
    tool: str
    status: str
    result: Any
    need_routing_check: bool
    attempt: int
    events: List[StateEvent] = field(default_factory=list)
    max_iterations: int = 12
    max_retries: int = 3
    plan: List[TaskAction] = field(default_factory=list)
    iteration: int = 0
    completed_steps: int = 0

    @classmethod
    def new(cls, goal: str, max_iterations: int, max_retries: int) -> "TaskState":
        return cls(
            request_id=str(uuid.uuid4()),
            goal=goal,
            state="received",
            next_action="router",
            model=DEFAULT_COORDINATOR_MODEL,
            tool="",
            status="queued",
            result=None,
            need_routing_check=False,
            attempt=0,
            max_iterations=max_iterations,
            max_retries=max_retries,
        )


@dataclass
class PlanResult:
    actions: List[TaskAction]
    rationale: str


def state_to_json_payload(state: TaskState) -> Dict[str, Any]:
    payload = asdict(state)
    payload["plan"] = [asdict(step) for step in state.plan]
    payload["events"] = [asdict(event) for event in state.events]
    return payload


def dump_state_line(
    state: TaskState,
    stage: str,
    message: str,
    details: Dict[str, Any] | None = None,
) -> str:
    payload: Dict[str, Any] = {
        "stage": stage,
        "request_id": state.request_id,
        "goal": state.goal,
        "state": state.state,
        "next_action": state.next_action,
        "model": state.model,
        "tool": state.tool,
        "status": state.status,
        "result": state.result,
        "need_routing_check": state.need_routing_check,
        "attempt": state.attempt,
        "details": details or {},
        "message": message,
        "iteration": state.iteration,
        "completed_steps": state.completed_steps,
    }
    return json.dumps(payload, ensure_ascii=False)
