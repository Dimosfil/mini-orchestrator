from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from .models import TaskAction
from .tools import ToolResult, ToolRuntime


@dataclass(frozen=True)
class ExecutionReport:
    action_id: str
    success: bool
    result: ToolResult | None
    error: str | None


class Executor:
    def __init__(self, tool_runtime: ToolRuntime):
        self._tool_runtime = tool_runtime

    def run_action(self, action: TaskAction) -> ExecutionReport:
        result = self._tool_runtime.execute(action.tool, action.args)
        return ExecutionReport(action_id=action.action_id, success=result.success, result=result, error=result.error)
