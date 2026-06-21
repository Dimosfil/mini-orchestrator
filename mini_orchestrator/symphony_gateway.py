from __future__ import annotations

from dataclasses import dataclass
from time import monotonic, sleep
from typing import Any, Callable

from .symphony_daemon import (
    SymphonyDaemonError,
    build_symphony_intake_payload,
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
                    message="Symphony no longer reports accepted issues as active.",
                )

            if self._clock() >= deadline:
                return SymphonyWaitResult(
                    status="timeout",
                    request_id=submit_result.request_id,
                    issues=[_active_issue_snapshot(last_state, issue_id) for issue_id in issue_ids],
                    state=last_state,
                    message="Timed out waiting for Symphony result.",
                )
            self._sleep(poll_interval_seconds)

    def run_and_wait(
        self,
        payload: dict[str, Any],
        *,
        state_url: str,
        timeout_seconds: float = 300.0,
        poll_interval_seconds: float = 5.0,
    ) -> SymphonyWaitResult:
        return self.wait_for_result(
            self.submit(payload),
            state_url=state_url,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
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


__all__ = [
    "SymphonyDaemonError",
    "SymphonyGateway",
    "SymphonySubmitResult",
    "SymphonyWaitResult",
]
