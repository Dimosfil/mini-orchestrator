from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable
import json


ACTIVE_STATUSES = {"queued", "planning", "running", "waiting_approval"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_read_events(path: Path, max_lines: int = 5000) -> Iterable[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            for index, line in enumerate(handle):
                if index >= max_lines:
                    break
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict):
                    yield event
    except OSError:
        return


def _notification_method(event: Dict[str, Any]) -> str:
    message = event.get("message")
    if not isinstance(message, dict):
        return ""
    return str(message.get("method") or "")


def _notification_item_type(event: Dict[str, Any]) -> str:
    message = event.get("message")
    if not isinstance(message, dict):
        return ""
    params = message.get("params")
    if not isinstance(params, dict):
        return ""
    item = params.get("item")
    if not isinstance(item, dict):
        return ""
    return str(item.get("type") or "")


def _event_thread_id(event: Dict[str, Any]) -> str:
    thread_id = str(event.get("threadId") or "")
    if thread_id:
        return thread_id
    message = event.get("message")
    if not isinstance(message, dict):
        return ""
    params = message.get("params")
    if not isinstance(params, dict):
        return ""
    return str(params.get("threadId") or "")


def _compact_task(task: str, limit: int = 160) -> str:
    task = " ".join(task.split())
    if len(task) <= limit:
        return task
    return task[: limit - 1].rstrip() + "..."


def _run_from_log(path: Path, root: Path) -> Dict[str, Any]:
    status = "queued"
    mode = "single"
    task = ""
    current_agent = ""
    last_event = ""
    last_error = ""
    last_event_time = ""
    has_final = False
    has_error = False
    waiting_approval = False
    workers: list[Dict[str, Any]] = []
    thread_to_agent: dict[str, str] = {}
    outputs: dict[str, str] = {}
    event_counts: dict[str, int] = {}
    approval_count = 0
    turn_count = 0
    token_total = 0

    for event in _safe_read_events(path):
        event_type = str(event.get("type") or "unknown")
        event_counts[event_type] = event_counts.get(event_type, 0) + 1
        last_event_time = str(event.get("time") or last_event_time)

        if event_type == "task_created":
            task = str(event.get("task") or "")
            if event.get("planOnly"):
                mode = "plan"
                status = "planning"
            elif event.get("chain"):
                mode = "chain"
                status = "queued"
            elif event.get("dryRun"):
                mode = "dry-run"
                status = "queued"
            else:
                status = "queued"
            last_event = "Task accepted"
        elif event_type == "dispatch_decision":
            last_event = f"Dispatch: {event.get('role') or '-'}"
        elif event_type == "agent_started":
            current_agent = str(event.get("agent") or current_agent)
            status = "running"
            last_event = f"{current_agent} started"
        elif event_type == "agent_thread_started":
            current_agent = str(event.get("agent") or current_agent)
            status = "running"
            thread_id = str(event.get("threadId") or "")
            if thread_id:
                thread_to_agent[thread_id] = current_agent
            workers.append(
                {
                    "agent": current_agent,
                    "model": event.get("model"),
                    "threadId": thread_id or None,
                }
            )
            last_event = f"{current_agent} thread started"
        elif event_type == "handoff":
            current_agent = str(event.get("to") or current_agent)
            status = "running"
            last_event = f"Handoff to {current_agent}"
        elif event_type == "agent_turn_started":
            current_agent = str(event.get("agent") or current_agent)
            status = "running"
            turn_count += 1
            last_event = f"{current_agent} turn started"
        elif event_type == "codex_notification":
            method = _notification_method(event)
            item_type = _notification_item_type(event)
            thread_agent = thread_to_agent.get(_event_thread_id(event), "")
            if thread_agent:
                current_agent = thread_agent
            if method == "item/fileChange/requestApproval":
                approval_count += 1
                waiting_approval = True
                status = "waiting_approval"
                last_event = f"{current_agent or 'worker'} waiting for file-change approval"
            elif method == "thread/tokenUsage/updated":
                message = event.get("message")
                params = message.get("params", {}) if isinstance(message, dict) else {}
                usage = params.get("tokenUsage", {}) if isinstance(params, dict) else {}
                total = usage.get("total", {}) if isinstance(usage, dict) else {}
                token_total = int(total.get("totalTokens") or token_total or 0)
                last_event = "Token usage updated"
            elif item_type:
                last_event = f"{current_agent or 'worker'} {item_type}"
            elif method:
                last_event = method
        elif event_type == "agent_result":
            current_agent = str(event.get("agent") or current_agent)
            output = str(event.get("output") or "")
            outputs[current_agent] = output
            status = "running"
            last_event = f"{current_agent} result returned"
        elif event_type == "final":
            has_final = True
            status = "done"
            last_event = "Workflow completed"
        elif event_type == "error":
            has_error = True
            last_error = str(event.get("error") or event.get("message") or "Dispatcher error")
            status = "failed"
            last_event = "Workflow failed"

    if waiting_approval and not has_final:
        status = "waiting_approval"
        if has_error and "Timed out" in last_error:
            last_event = "Executor approval gate is still visible in worker thread"

    try:
        log_value = str(path.relative_to(root))
    except ValueError:
        log_value = str(path)

    return {
        "runId": path.stem,
        "status": status,
        "mode": mode,
        "currentAgent": current_agent or None,
        "task": {
            "taskId": path.stem,
            "title": _compact_task(task) or path.stem,
            "raw": task,
        },
        "profileSnapshotId": current_agent or "dispatcher",
        "thread": {
            "threadId": workers[-1]["threadId"] if workers else None,
            "turnCount": turn_count,
            "workers": workers,
        },
        "tokens": {"total": token_total},
        "artifacts": {"eventLogPath": log_value},
        "lastEvent": last_event or "No events yet",
        "lastError": last_error if status == "failed" else "",
        "approval": {
            "required": waiting_approval and not has_final,
            "count": approval_count,
        },
        "eventTypes": event_counts,
        "updatedAt": last_event_time,
        "outputs": outputs,
    }


def build_dispatcher_live_runs(root: Path, limit: int = 8) -> Dict[str, Any]:
    runs_dir = root / "tools" / "codex-dispatcher" / "runs"
    log_paths = sorted(
        runs_dir.glob("*.jsonl"),
        key=lambda item: item.stat().st_mtime if item.exists() else 0,
        reverse=True,
    )[:limit]
    runs = [_run_from_log(path, root) for path in log_paths]
    summary = {
        "total": len(runs),
        "active": sum(1 for run in runs if run["status"] in ACTIVE_STATUSES),
        "blocked": sum(1 for run in runs if run["status"] == "waiting_approval"),
        "done": sum(1 for run in runs if run["status"] == "done"),
        "failed": sum(1 for run in runs if run["status"] == "failed"),
    }
    profiles = {
        "dispatcher": {"displayName": "Dispatcher", "role": "dispatcher", "model": "-"},
        "planner": {"displayName": "Planner", "role": "planner", "model": "gpt-5.5"},
        "executor": {"displayName": "Executor", "role": "executor", "model": "gpt-5.4"},
        "reviewer": {"displayName": "Reviewer", "role": "reviewer", "model": "gpt-5.4-mini"},
    }
    return {
        "source": "dispatcher-jsonl",
        "generatedAt": _utc_now(),
        "summary": summary,
        "profiles": profiles,
        "runs": runs,
    }
