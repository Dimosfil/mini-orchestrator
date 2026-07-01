from __future__ import annotations

from dataclasses import dataclass
from time import monotonic, sleep
from typing import Any, Callable

from .symphony_daemon import (
    SymphonyDaemonError,
    build_symphony_handoff_payload,
    build_symphony_intake_payload,
    build_task_checklist,
    fetch_symphony_issue,
    fetch_symphony_state,
    submit_symphony_intake,
)


STATE_BUCKETS = ("running", "retrying", "blocked")


@dataclass(frozen=True)
class SymphonySubmitResult:
    request_id: str
    accepted: list[dict[str, Any]]
    blocked: list[dict[str, Any]]
    raw: dict[str, Any]


@dataclass(frozen=True)
class SymphonyWaitResult:
    status: str
    request_id: str
    issues: list[dict[str, Any]]
    state: dict[str, Any]
    message: str = ""


@dataclass(frozen=True)
class SymphonyChainResult:
    status: str
    request_id: str
    checklist: list[dict[str, Any]]
    outputs: list[dict[str, Any]]
    steps: list[dict[str, Any]]
    message: str = ""


class SymphonyGateway:
    """Small integration boundary for Symphony task intake and result polling."""

    def __init__(
        self,
        *,
        submit_func: Callable[[dict[str, Any]], dict[str, Any]] = submit_symphony_intake,
        state_func: Callable[[str], dict[str, Any]] = fetch_symphony_state,
        issue_func: Callable[[str], dict[str, Any]] = fetch_symphony_issue,
        sleeper: Callable[[float], None] = sleep,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._submit_func = submit_func
        self._state_func = state_func
        self._issue_func = issue_func
        self._sleep = sleeper
        self._clock = clock

    def build_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return build_symphony_intake_payload(payload)

    def submit(self, payload: dict[str, Any]) -> SymphonySubmitResult:
        submission = self._submit_func(payload)
        response = submission.get("response") if isinstance(submission.get("response"), dict) else {}
        accepted = response.get("accepted") if isinstance(response.get("accepted"), list) else []
        blocked = response.get("blocked") if isinstance(response.get("blocked"), list) else []
        request_id = str(response.get("request_id") or response.get("requestId") or "").strip()
        if not request_id:
            request_id = str(submission.get("externalRunId") or submission.get("runId") or "").strip()
        return SymphonySubmitResult(
            request_id=request_id,
            accepted=[item for item in accepted if isinstance(item, dict)],
            blocked=[item for item in blocked if isinstance(item, dict)],
            raw=submission,
        )

    def wait_for_result(
        self,
        submit_result: SymphonySubmitResult,
        *,
        state_url: str,
        timeout_seconds: float = 300.0,
        active_grace_seconds: float = 0.0,
        poll_interval_seconds: float = 5.0,
    ) -> SymphonyWaitResult:
        issue_refs = _accepted_issue_refs(submit_result.accepted)
        issue_ids = [ref["state_id"] for ref in issue_refs if ref["state_id"]]
        if not issue_ids:
            return SymphonyWaitResult(
                status="blocked",
                request_id=submit_result.request_id,
                issues=submit_result.blocked,
                state={},
                message="Symphony intake returned no accepted issue ids.",
            )

        deadline = self._clock() + timeout_seconds
        hard_deadline = deadline + max(0.0, active_grace_seconds)
        soft_timeout_reached = False
        last_state: dict[str, Any] = {}
        while True:
            last_state = self._state_func(state_url)
            active = _active_issue_ids(last_state)
            blocked = _blocked_issues(last_state, issue_ids)
            if blocked:
                return SymphonyWaitResult(
                    status="blocked",
                    request_id=submit_result.request_id,
                    issues=blocked,
                    state=last_state,
                    message="One or more Symphony issues are blocked.",
                )

            if not any(issue_id in active for issue_id in issue_ids):
                issues: list[dict[str, Any]] = []
                missing_results: list[dict[str, Any]] = []
                for ref in issue_refs:
                    if not ref["fetch_id"]:
                        continue
                    try:
                        issues.append(self._issue_func(ref["fetch_id"]))
                    except SymphonyDaemonError as exc:
                        missing_results.append(
                            {
                                "issue_id": ref["state_id"],
                                "issue_identifier": ref["fetch_id"],
                                "error": str(exc),
                            }
                        )
                if missing_results and not issues:
                    return SymphonyWaitResult(
                        status="completed_without_result",
                        request_id=submit_result.request_id,
                        issues=missing_results,
                        state=last_state,
                        message="Symphony stopped reporting accepted issues as active, but its issue endpoint did not return completed result details.",
                    )
                status = _terminal_status(issues)
                return SymphonyWaitResult(
                    status=status,
                    request_id=submit_result.request_id,
                    issues=issues,
                    state=last_state,
                    message=(
                        "Symphony completed after the soft timeout grace period."
                        if soft_timeout_reached
                        else "Symphony no longer reports accepted issues as active."
                    ),
                )

            now = self._clock()
            if now >= deadline and now < hard_deadline:
                soft_timeout_reached = True
                self._sleep(poll_interval_seconds)
                continue

            if now >= hard_deadline:
                return SymphonyWaitResult(
                    status="timeout",
                    request_id=submit_result.request_id,
                    issues=[_active_issue_snapshot(last_state, issue_id) for issue_id in issue_ids],
                    state=last_state,
                    message=(
                        "Timed out waiting for Symphony result after the active grace period."
                        if active_grace_seconds > 0
                        else "Timed out waiting for Symphony result."
                    ),
                )
            self._sleep(poll_interval_seconds)

    def run_and_wait(
        self,
        payload: dict[str, Any],
        *,
        state_url: str,
        timeout_seconds: float = 300.0,
        active_grace_seconds: float = 0.0,
        poll_interval_seconds: float = 5.0,
    ) -> SymphonyWaitResult:
        return self.wait_for_result(
            self.submit(payload),
            state_url=state_url,
            timeout_seconds=timeout_seconds,
            active_grace_seconds=active_grace_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )

    def run_mini_owned_chain(
        self,
        payload: dict[str, Any],
        *,
        state_url: str,
        timeout_per_step_seconds: float = 300.0,
        active_grace_seconds: float = 0.0,
        poll_interval_seconds: float = 5.0,
    ) -> SymphonyChainResult:
        checklist = build_task_checklist(payload)
        previous_outputs: list[dict[str, Any]] = []
        steps: list[dict[str, Any]] = []
        request_ids: list[str] = []
        agent_index = 0
        while True:
            try:
                handoff_payload = build_symphony_handoff_payload(
                    payload,
                    agent_index=agent_index,
                    checklist_item=checklist[0],
                    previous_outputs=previous_outputs,
                )
            except IndexError:
                break

            agent_task = handoff_payload["agentTasks"][0]
            agent = agent_task.get("agent") if isinstance(agent_task.get("agent"), dict) else {}
            submit_result = self.submit(handoff_payload)
            request_ids.append(submit_result.request_id)
            wait_result = self.wait_for_result(
                submit_result,
                state_url=state_url,
                timeout_seconds=timeout_per_step_seconds,
                active_grace_seconds=active_grace_seconds,
                poll_interval_seconds=poll_interval_seconds,
            )
            output = {
                "agentIndex": agent_index,
                "agentId": str(agent.get("id") or ""),
                "agentName": str(agent.get("name") or agent.get("role") or ""),
                "status": wait_result.status,
                "summary": _issues_summary(wait_result.issues),
                "issues": wait_result.issues,
                "requestId": submit_result.request_id,
            }
            previous_outputs.append(output)
            steps.append(
                {
                    "agentIndex": agent_index,
                    "agent": agent,
                    "requestId": submit_result.request_id,
                    "status": wait_result.status,
                    "message": wait_result.message,
                }
            )
            if wait_result.status not in {"done", "completed"}:
                checklist[0]["status"] = "blocked" if wait_result.status == "blocked" else "failed"
                return SymphonyChainResult(
                    status=wait_result.status,
                    request_id=",".join([item for item in request_ids if item]),
                    checklist=checklist,
                    outputs=previous_outputs,
                    steps=steps,
                    message=wait_result.message,
                )
            agent_index += 1

        checklist[0]["status"] = "done"
        return SymphonyChainResult(
            status="done",
            request_id=",".join([item for item in request_ids if item]),
            checklist=checklist,
            outputs=previous_outputs,
            steps=steps,
            message="Mini Orchestrator completed the selected preset chain through sequential Symphony handoffs.",
        )


def _accepted_issue_refs(accepted: list[dict[str, Any]]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for item in accepted:
        state_id = str(item.get("issue_id") or item.get("identifier") or item.get("issueIdentifier") or "").strip()
        fetch_id = str(item.get("identifier") or item.get("issueIdentifier") or item.get("issue_id") or "").strip()
        if state_id:
            refs.append({"state_id": state_id, "fetch_id": fetch_id or state_id})
    return refs


def _entries(state: dict[str, Any], bucket: str) -> list[dict[str, Any]]:
    value = state.get(bucket)
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _entry_issue_id(entry: dict[str, Any]) -> str:
    return str(entry.get("issue_id") or entry.get("issue_identifier") or entry.get("identifier") or "").strip()


def _active_issue_ids(state: dict[str, Any]) -> set[str]:
    issue_ids: set[str] = set()
    for bucket in STATE_BUCKETS:
        for entry in _entries(state, bucket):
            issue_id = _entry_issue_id(entry)
            if issue_id:
                issue_ids.add(issue_id)
    return issue_ids


def _blocked_issues(state: dict[str, Any], expected_issue_ids: list[str]) -> list[dict[str, Any]]:
    expected = set(expected_issue_ids)
    return [entry for entry in _entries(state, "blocked") if _entry_issue_id(entry) in expected]


def _active_issue_snapshot(state: dict[str, Any], issue_id: str) -> dict[str, Any]:
    for bucket in STATE_BUCKETS:
        for entry in _entries(state, bucket):
            if _entry_issue_id(entry) == issue_id:
                return entry
    return {"issue_id": issue_id}


def _terminal_status(issues: list[dict[str, Any]]) -> str:
    if any(_issue_failed(issue) for issue in issues):
        return "failed"
    if all(_issue_done(issue) for issue in issues):
        return "done"
    return "completed"


def _issue_done(issue: dict[str, Any]) -> bool:
    text = " ".join(str(issue.get(key) or "") for key in ("state", "status", "last_event", "lastEvent")).casefold()
    return any(marker in text for marker in ("done", "complete", "completed", "resolved", "closed"))


def _issue_failed(issue: dict[str, Any]) -> bool:
    text = " ".join(str(issue.get(key) or "") for key in ("state", "status", "error", "last_event", "lastEvent")).casefold()
    return any(marker in text for marker in ("failed", "error", "cancelled", "canceled"))


def _issues_summary(issues: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for issue in issues:
        for key in ("final_message", "last_message", "summary", "last_event", "state", "status"):
            value = issue.get(key)
            if value:
                parts.append(str(value))
                break
    return "\n".join(parts)


__all__ = [
    "SymphonyDaemonError",
    "SymphonyGateway",
    "SymphonyChainResult",
    "SymphonySubmitResult",
    "SymphonyWaitResult",
]
