from __future__ import annotations

from pathlib import Path
from typing import Dict

from .config import OrchestratorConfig
from .executor import Executor
from .llm import OpenAiResponsesClient
from .models import StateEvent, TaskState, dump_state_line, state_to_json_payload
from .planner import Planner
from .router import Router
from .tools import ToolRuntime
from .validator import Validator


class Orchestrator:
    def __init__(self, config: OrchestratorConfig, log_path: Path | None = None):
        self.config = config
        self.tool_runtime = ToolRuntime(config)
        self.executor = Executor(self.tool_runtime)
        self.llm_client = OpenAiResponsesClient(config)
        self.planner = Planner(
            workspace_root=config.workspace_root,
            coordinator_model=config.coordinator_model,
            executor_model=config.executor_model,
            llm_client=self.llm_client,
        )
        self.router = Router()
        self.validator = Validator()
        self.log_path = log_path
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _append_log(self, state: TaskState, stage: str, message: str, details: Dict | None = None) -> None:
        if not self.log_path:
            return
        line = dump_state_line(state=state, stage=stage, message=message, details=details)
        with self.log_path.open("a", encoding="utf-8") as file:
            file.write(line + "\n")

    def _record(self, state: TaskState, stage: str, status: str, message: str, details: Dict | None = None) -> None:
        state.events.append(StateEvent(stage=stage, status=status, message=message, attempt=state.attempt, details=details or {}))
        self._append_log(state=state, stage=stage, message=message, details=details)

    def run(self, goal: str) -> TaskState:
        state = TaskState.new(
            goal=goal,
            max_iterations=self.config.max_iterations,
            max_retries=self.config.max_retries,
        )
        state.model = self.config.coordinator_model
        state.state = "routing"
        state.status = "routed"
        self._record(state, "router", "routed", f"Routing decision started for goal: {goal}")

        decision = self.router.route_goal(goal)
        state.model = decision.model
        state.next_action = "plan"
        state.status = "planning"
        self._record(state, "router", "plan", decision.reason)

        planned = self.planner.plan(goal)
        state.plan = planned.actions
        state.result = {"plan_rationale": planned.rationale, "plan_size": len(state.plan)}
        state.state = "planned"
        state.status = "plan_ready"
        state.next_action = state.plan[0].description if state.plan else "noop"
        self._record(state, "planner", "ready", planned.rationale, details={"plan_count": len(state.plan)})

        for step_index, action in enumerate(state.plan):
            if state.iteration >= state.max_iterations:
                state.state = "finished"
                state.status = "failed"
                state.result = {"final_error": "Max iterations reached.", "plan": state.plan}
                self._record(state, "orchestrator", "failed", "Maximum iteration limit reached.")
                break

            if action.tool == "noop":
                state.model = action.model
                state.tool = action.tool
                state.next_action = action.description
                state.state = "needs_routing"
                state.status = "needs_routing_check"
                state.need_routing_check = True
                self._record(
                    state,
                    "planner",
                    "needs_input",
                    action.description,
                    details={"goal": goal},
                )
                break

            action_attempt = 0
            while action_attempt <= state.max_retries:
                state.iteration += 1
                state.attempt = action_attempt
                state.model = action.model
                state.next_action = action.description
                state.tool = action.tool
                state.state = "executing"
                state.status = "in_progress"
                self._record(state, "executor", "start", f"Step {step_index + 1}/{len(state.plan)} started", {"tool": action.tool})

                report = self.executor.run_action(action)
                validation = self.validator.validate(action, report)
                state.result = {
                    "action": action.description,
                    "tool_output": report.result.output if report.result else "",
                    "tool_metadata": report.result.metadata if report.result else {},
                    "validation": {
                        "status": validation.status,
                        "message": validation.message,
                    },
                }
                state.need_routing_check = validation.need_retry

                if validation.passed:
                    state.completed_steps += 1
                    state.status = "step_ok"
                    self._record(
                        state,
                        "validator",
                        "ok",
                        validation.message,
                        {"action_step": step_index},
                    )
                    break

                state.status = "step_failed"
                self._record(
                    state,
                    "validator",
                    "fail",
                    validation.message,
                    {"action_step": step_index, "attempt": action_attempt},
                )
                action_attempt += 1
                state.attempt = action_attempt
                state.need_routing_check = validation.need_retry

                if action_attempt <= state.max_retries and validation.need_retry:
                    state.status = "retrying"
                    continue

                state.state = "failed"
                break

            if state.state == "failed":
                break

        if state.completed_steps == len(state.plan):
            state.state = "finished"
            state.status = "done"
            state.need_routing_check = False
        elif state.status == "needs_routing_check":
            state.state = "needs_routing_check"
        elif state.status not in {"done", "failed", "needs_routing_check"}:
            state.state = "finished"
            state.status = "failed"

        if state.state != "needs_routing_check":
            self._record(
                state,
                "orchestrator",
                state.status,
                f"Completed {state.completed_steps}/{len(state.plan)} steps",
            )

        state.result = state.result or {}
        state.next_action = "idle" if state.status == "done" else state.next_action
        return state

    def to_dict(self, state: TaskState) -> Dict:
        return state_to_json_payload(state)
