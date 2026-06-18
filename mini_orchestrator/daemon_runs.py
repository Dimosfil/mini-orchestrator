from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_state(
    *,
    run_id: str,
    task_id: str,
    sprint_id: str,
    profile_snapshot_id: str,
    status: str,
    workspace_path: str,
    thread_id: str | None,
    turn_id: str | None,
    turn_count: int,
    input_tokens: int,
    output_tokens: int,
    last_event: str | None,
    last_error: str | None,
    event_log_path: str,
    created_at: str,
    updated_at: str,
) -> Dict[str, Any]:
    total_tokens = input_tokens + output_tokens
    return {
        "schemaVersion": 1,
        "runId": run_id,
        "task": {
            "taskId": task_id,
            "sprintId": sprint_id,
            "project": "mini-orchestrator",
        },
        "profileSnapshotId": profile_snapshot_id,
        "status": status,
        "workspacePath": workspace_path,
        "thread": {
            "threadId": thread_id,
            "currentTurnId": turn_id,
            "turnCount": turn_count,
        },
        "tokens": {
            "input": input_tokens,
            "output": output_tokens,
            "total": total_tokens,
        },
        "lastEvent": last_event,
        "lastError": last_error,
        "artifacts": {
            "eventLogPath": event_log_path,
            "workspaceGenerated": True,
            "durableProjectMemory": False,
            "privateRuntimeData": True,
        },
        "createdAt": created_at,
        "updatedAt": updated_at,
    }


def build_demo_daemon_runs() -> Dict[str, Any]:
    """Return schema-shaped run states until the real daemon registry exists."""
    generated_at = _utc_now()
    runs: List[Dict[str, Any]] = [
        _run_state(
            run_id="run-demo-planner-001",
            task_id="worknest-demo-001",
            sprint_id="sprint-agent-cards-as-worker-profiles",
            profile_snapshot_id="profile-planner-demo",
            status="running",
            workspace_path="generated-workspaces/run-demo-planner-001",
            thread_id="codex-thread-demo-planner",
            turn_id="codex-turn-demo-plan",
            turn_count=1,
            input_tokens=1840,
            output_tokens=620,
            last_event="turn_started",
            last_error=None,
            event_log_path="runtime/daemon-runs/run-demo-planner-001.jsonl",
            created_at="2026-06-18T17:10:00Z",
            updated_at=generated_at,
        ),
        _run_state(
            run_id="run-demo-executor-002",
            task_id="worknest-demo-002",
            sprint_id="sprint-agent-cards-as-worker-profiles",
            profile_snapshot_id="profile-executor-demo",
            status="blocked",
            workspace_path="generated-workspaces/run-demo-executor-002",
            thread_id="codex-thread-demo-executor",
            turn_id="codex-turn-demo-impl",
            turn_count=3,
            input_tokens=5270,
            output_tokens=1410,
            last_event="blocked",
            last_error="Waiting for an approved WorkNest progress-update contract.",
            event_log_path="runtime/daemon-runs/run-demo-executor-002.jsonl",
            created_at="2026-06-18T17:02:00Z",
            updated_at=generated_at,
        ),
        _run_state(
            run_id="run-demo-reviewer-003",
            task_id="worknest-demo-003",
            sprint_id="sprint-agent-cards-as-worker-profiles",
            profile_snapshot_id="profile-reviewer-demo",
            status="done",
            workspace_path="generated-workspaces/run-demo-reviewer-003",
            thread_id="codex-thread-demo-reviewer",
            turn_id="codex-turn-demo-review",
            turn_count=2,
            input_tokens=3120,
            output_tokens=880,
            last_event="task_completed",
            last_error=None,
            event_log_path="runtime/daemon-runs/run-demo-reviewer-003.jsonl",
            created_at="2026-06-18T16:42:00Z",
            updated_at="2026-06-18T16:55:00Z",
        ),
    ]
    profiles = {
        "profile-planner-demo": {
            "displayName": "Planner Demo",
            "role": "Planner",
            "model": "gpt-5.5",
        },
        "profile-executor-demo": {
            "displayName": "Executor Demo",
            "role": "Executor",
            "model": "gpt-5.4",
        },
        "profile-reviewer-demo": {
            "displayName": "Reviewer Demo",
            "role": "Reviewer",
            "model": "gpt-5.4-mini",
        },
    }
    active_statuses = {"queued", "claimed", "running", "blocked", "retrying"}
    summary = {
        "total": len(runs),
        "active": sum(1 for run in runs if run["status"] in active_statuses),
        "blocked": sum(1 for run in runs if run["status"] == "blocked"),
        "done": sum(1 for run in runs if run["status"] == "done"),
        "failed": sum(1 for run in runs if run["status"] == "failed"),
    }
    return {
        "service": "mini-orchestrator",
        "source": "demo",
        "generatedAt": generated_at,
        "summary": summary,
        "profiles": profiles,
        "runs": runs,
    }
