from __future__ import annotations

from dataclasses import dataclass

from .executor import ExecutionReport
from .models import TaskAction


@dataclass(frozen=True)
class ValidationDecision:
    passed: bool
    status: str
    message: str
    need_retry: bool = False


class Validator:
    def _command_error_is_retryable(self, message: str) -> bool:
        lowered = message.lower()
        if not lowered:
            return False
        return "timeout" in lowered or "timed out" in lowered or "command execution error" in lowered

    def validate(self, action: TaskAction, report: ExecutionReport) -> ValidationDecision:
        if report.result is None:
            return ValidationDecision(
                passed=False,
                status="failed",
                message="No execution result available.",
                need_retry=False,
            )

        if report.result.success:
            return ValidationDecision(passed=True, status="ok", message="Execution succeeded.")

        if not report.error:
            return ValidationDecision(
                passed=False,
                status="failed",
                message="Execution failed without diagnostics.",
                need_retry=True,
            )

        lowered_error = report.error.lower()
        if action.tool == "run_command":
            return ValidationDecision(
                passed=False,
                status="failed",
                message=report.error,
                need_retry=self._command_error_is_retryable(report.error),
            )

        if action.tool == "apply_patch" and any(
            marker in lowered_error for marker in ("old content block was not found", "not found", "outside allowed")
        ):
            return ValidationDecision(
                passed=False,
                status="failed",
                message=report.error,
                need_retry=False,
            )

        return ValidationDecision(passed=False, status="failed", message=report.error, need_retry=True)
