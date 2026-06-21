from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable
import json
import os


ACTIVE_STATUSES = {"queued", "planning", "running", "waiting_approval"}
CHAIN_AGENTS = ["planner", "executor", "reviewer"]
DEFAULT_STALE_AFTER_SECONDS = 15 * 60


def _env_optional(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def _default_stage_model(agent: str) -> str | None:
    if agent == "planner":
        return _env_optional("MINI_ORCHESTRATOR_COORDINATOR_MODEL")
    if agent == "executor":
        return _env_optional("MINI_ORCHESTRATOR_EXECUTOR_MODEL")
    if agent == "reviewer":
        return _env_optional("MINI_ORCHESTRATOR_REVIEWER_MODEL")
    return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_time(value: str) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _stale_after_seconds() -> int:
    raw = os.environ.get("MINI_ORCHESTRATOR_DISPATCHER_STALE_AFTER_SECONDS", "").strip()
    if not raw:
        return DEFAULT_STALE_AFTER_SECONDS
    try:
        return max(30, int(raw))
    except ValueError:
        return DEFAULT_STALE_AFTER_SECONDS


def _process_is_running(process_id: int | None) -> bool | None:
    if not process_id:
        return None
    try:
        os.kill(process_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None
    return True


def _stale_reason(
    *,
    status: str,
    process_id: int | None,
    last_event_time: str,
    now: datetime,
) -> str:
    if status not in ACTIVE_STATUSES:
        return ""
    process_status = _process_is_running(process_id)
    if process_status is False:
        return f"dispatcher process {process_id} is not running"

    parsed = _parse_time(last_event_time)
    if parsed is None:
        return "dispatcher log has no readable event timestamp"
    age_seconds = int((now - parsed).total_seconds())
    threshold = _stale_after_seconds()
    if age_seconds > threshold:
        return f"dispatcher log has not updated for {age_seconds}s"
    return ""


def _safe_read_events(path: Path, max_lines: int = 50000) -> Iterable[Dict[str, Any]]:
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


def _stage_label(agent: str) -> str:
    labels = {
        "planner": "Planner",
        "executor": "Executor",
        "reviewer": "Reviewer",
        "dispatcher": "Dispatcher",
        "visual-agent": "Visual Agent",
    }
    return labels.get(agent, agent.replace("-", " ").title())


def _stage_status_label(status: str) -> str:
    labels = {
        "pending": "Pending",
        "running": "Running",
        "waiting_approval": "Waiting approval",
        "done": "Done",
        "failed": "Failed",
    }
    return labels.get(status, status.replace("_", " ").title())


def _ensure_stage(
    stage_map: Dict[str, Dict[str, Any]],
    stage_order: list[str],
    agent: str,
) -> Dict[str, Any]:
    if agent not in stage_map:
        stage_map[agent] = {
            "agent": agent,
            "label": _stage_label(agent),
            "status": "pending",
            "statusLabel": "Pending",
            "startedAt": None,
            "completedAt": None,
            "threadId": None,
            "turnCount": 0,
            "model": _default_stage_model(agent),
            "tokens": 0,
            "lastEvent": "",
            "output": "",
        }
        stage_order.append(agent)
    return stage_map[agent]


def _set_stage_status(stage: Dict[str, Any], status: str, event_time: str) -> None:
    current_status = str(stage.get("status") or "pending")
    if current_status == "done" and status not in {"failed", "waiting_approval"}:
        return
    if current_status == "waiting_approval" and status == "running":
        return
    stage["status"] = status
    stage["statusLabel"] = _stage_status_label(status)
    if status in {"running", "waiting_approval"} and not stage.get("startedAt"):
        stage["startedAt"] = event_time or None
    if status in {"done", "failed"}:
        stage["completedAt"] = event_time or None


def _touch_stage(
    stage_map: Dict[str, Dict[str, Any]],
    stage_order: list[str],
    agent: str,
    status: str,
    event_time: str,
    *,
    model: Any = None,
    thread_id: str = "",
    last_event: str = "",
    output: str = "",
    tokens: int | None = None,
    turn_increment: int = 0,
) -> None:
    if not agent:
        return
    stage = _ensure_stage(stage_map, stage_order, agent)
    _set_stage_status(stage, status, event_time)
    if model:
        stage["model"] = model
    if thread_id:
        stage["threadId"] = thread_id
    if last_event:
        stage["lastEvent"] = last_event
    if output:
        stage["output"] = output
    if tokens is not None:
        stage["tokens"] = tokens
    if turn_increment:
        stage["turnCount"] = int(stage.get("turnCount") or 0) + turn_increment


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
    stage_map: Dict[str, Dict[str, Any]] = {}
    stage_order: list[str] = []
    profile_snapshot_id = ""
    chain_preset: dict[str, Any] = {}
    approval_count = 0
    turn_count = 0
    token_total = 0
    first_event_time = ""
    process_id: int | None = None

    for event in _safe_read_events(path):
        event_type = str(event.get("type") or "unknown")
        event_counts[event_type] = event_counts.get(event_type, 0) + 1
        last_event_time = str(event.get("time") or last_event_time)
        if not first_event_time and last_event_time:
            first_event_time = last_event_time

        if event_type == "task_created":
            task = str(event.get("task") or "")
            profile_snapshot_id = str(event.get("profileSnapshotId") or profile_snapshot_id)
            event_mode = str(event.get("mode") or "")
            if event_mode == "visual-agent-task":
                mode = "visual-agent-task"
                status = "queued"
                visual_agent_name = str(event.get("visualAgentName") or "")
                if visual_agent_name:
                    _ensure_stage(stage_map, stage_order, visual_agent_name)
            elif event.get("planOnly"):
                mode = "plan"
                status = "planning"
                _ensure_stage(stage_map, stage_order, "planner")
            elif event.get("chain"):
                mode = "chain"
                status = "queued"
                for agent in CHAIN_AGENTS:
                    _ensure_stage(stage_map, stage_order, agent)
            elif event.get("dryRun"):
                mode = "dry-run"
                status = "queued"
            else:
                status = "queued"
            last_event = "Task accepted"
        elif event_type == "chain_selected":
            value = event.get("chainPreset")
            if isinstance(value, dict):
                chain_preset = value
                last_event = f"Chain selected: {value.get('name') or value.get('id') or 'agent chain'}"
        elif event_type == "dispatcher_process_started":
            try:
                process_id = int(event.get("processId") or 0) or None
            except (TypeError, ValueError):
                process_id = None
            last_event = "Dispatcher process started"
        elif event_type == "dispatch_decision":
            last_event = f"Dispatch: {event.get('role') or '-'}"
            role = str(event.get("role") or "")
            if role:
                _ensure_stage(stage_map, stage_order, role)
        elif event_type == "agent_started":
            current_agent = str(event.get("agent") or current_agent)
            status = "running"
            last_event = f"{current_agent} started"
            _touch_stage(stage_map, stage_order, current_agent, "running", last_event_time, last_event=last_event)
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
                    "profileSnapshotId": event.get("profileSnapshotId") or profile_snapshot_id or None,
                }
            )
            profile_snapshot_id = str(event.get("profileSnapshotId") or profile_snapshot_id)
            last_event = f"{current_agent} thread started"
            _touch_stage(
                stage_map,
                stage_order,
                current_agent,
                "running",
                last_event_time,
                model=event.get("model"),
                thread_id=thread_id,
                last_event=last_event,
            )
        elif event_type == "handoff":
            current_agent = str(event.get("to") or current_agent)
            profile_snapshot_id = str(event.get("profileSnapshotId") or profile_snapshot_id)
            status = "running"
            last_event = f"Handoff to {current_agent}"
            _touch_stage(stage_map, stage_order, current_agent, "running", last_event_time, last_event=last_event)
        elif event_type == "agent_turn_started":
            current_agent = str(event.get("agent") or current_agent)
            status = "running"
            turn_count += 1
            last_event = f"{current_agent} turn started"
            _touch_stage(
                stage_map,
                stage_order,
                current_agent,
                "running",
                last_event_time,
                thread_id=str(event.get("threadId") or ""),
                last_event=last_event,
                turn_increment=1,
            )
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
                _touch_stage(
                    stage_map,
                    stage_order,
                    current_agent or "worker",
                    "waiting_approval",
                    last_event_time,
                    last_event=last_event,
                )
            elif method == "thread/tokenUsage/updated":
                message = event.get("message")
                params = message.get("params", {}) if isinstance(message, dict) else {}
                usage = params.get("tokenUsage", {}) if isinstance(params, dict) else {}
                total = usage.get("total", {}) if isinstance(usage, dict) else {}
                token_total = int(total.get("totalTokens") or token_total or 0)
                last_event = "Token usage updated"
                _touch_stage(
                    stage_map,
                    stage_order,
                    current_agent or "worker",
                    "running",
                    last_event_time,
                    last_event=last_event,
                    tokens=token_total,
                )
            elif item_type:
                last_event = f"{current_agent or 'worker'} {item_type}"
                _touch_stage(
                    stage_map,
                    stage_order,
                    current_agent or "worker",
                    "running",
                    last_event_time,
                    last_event=last_event,
                )
            elif method:
                last_event = method
        elif event_type == "agent_result":
            current_agent = str(event.get("agent") or current_agent)
            output = str(event.get("output") or "")
            outputs[current_agent] = output
            status = "running"
            last_event = f"{current_agent} result returned"
            _touch_stage(
                stage_map,
                stage_order,
                current_agent,
                "done",
                last_event_time,
                last_event=last_event,
                output=output,
            )
        elif event_type == "final":
            has_final = True
            status = "done"
            last_event = "Workflow completed"
            final_outputs = event.get("outputs")
            if isinstance(final_outputs, dict):
                for agent, output in final_outputs.items():
                    agent_name = str(agent)
                    output_text = str(output or "")
                    outputs[agent_name] = output_text
                    _touch_stage(
                        stage_map,
                        stage_order,
                        agent_name,
                        "done",
                        last_event_time,
                        last_event=f"{agent_name} result returned",
                        output=output_text,
                    )
        elif event_type == "error":
            has_error = True
            last_error = str(event.get("error") or event.get("message") or "Dispatcher error")
            status = "failed"
            last_event = "Workflow failed"
            _touch_stage(
                stage_map,
                stage_order,
                current_agent or "dispatcher",
                "failed",
                last_event_time,
                last_event=last_error,
            )

    if waiting_approval and not has_final:
        status = "waiting_approval"
        if has_error and "Timed out" in last_error:
            last_event = "Executor approval gate is still visible in worker thread"
        _touch_stage(
            stage_map,
            stage_order,
            current_agent or "worker",
            "waiting_approval",
            last_event_time,
            last_event=last_event,
        )

    if has_final:
        for agent in stage_order:
            stage = stage_map[agent]
            if stage.get("status") in {"running", "waiting_approval"}:
                _set_stage_status(stage, "done", last_event_time)

    stale = {"isStale": False, "reason": "", "lastEventAt": last_event_time, "thresholdSeconds": _stale_after_seconds()}
    reason = _stale_reason(
        status=status,
        process_id=process_id,
        last_event_time=last_event_time,
        now=datetime.now(timezone.utc),
    )
    if reason:
        stale["isStale"] = True
        stale["reason"] = reason
        status = "stale"
        last_error = reason
        last_event = f"Stale run: {reason}"
        if current_agent:
            _touch_stage(stage_map, stage_order, current_agent, "failed", last_event_time, last_event=last_event)

    stages = [stage_map[agent] for agent in stage_order]

    try:
        log_value = str(path.relative_to(root))
    except ValueError:
        log_value = str(path)

    return {
        "schemaVersion": 1,
        "runId": path.stem,
        "sourceKey": "dispatcher",
        "sourceLabel": "Dispatcher",
        "status": status,
        "mode": mode,
        "currentAgent": current_agent or None,
        "task": {
            "taskId": path.stem,
            "title": _compact_task(task) or path.stem,
            "raw": task,
        },
        "profileSnapshotId": profile_snapshot_id or current_agent or "dispatcher",
        "thread": {
            "threadId": workers[-1]["threadId"] if workers else None,
            "turnCount": turn_count,
            "workers": workers,
            "processId": process_id,
        },
        "tokens": {"total": token_total},
        "artifacts": {"eventLogPath": log_value},
        "lastEvent": last_event or "No events yet",
        "lastError": last_error if status == "failed" else "",
        "approval": {
            "required": waiting_approval and not has_final,
            "count": approval_count,
        },
        "chainPreset": chain_preset,
        "stages": stages,
        "eventTypes": event_counts,
        "createdAt": first_event_time or last_event_time,
        "updatedAt": last_event_time,
        "stale": stale,
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
        "stale": sum(1 for run in runs if run["status"] == "stale"),
    }
    profiles = {
        "dispatcher": {"displayName": "Dispatcher", "role": "dispatcher", "model": "-"},
        "planner": {"displayName": "Planner", "role": "planner", "model": _default_stage_model("planner")},
        "executor": {"displayName": "Executor", "role": "executor", "model": _default_stage_model("executor")},
        "reviewer": {"displayName": "Reviewer", "role": "reviewer", "model": _default_stage_model("reviewer")},
    }
    return {
        "source": "dispatcher-jsonl",
        "generatedAt": _utc_now(),
        "summary": summary,
        "profiles": profiles,
        "runs": runs,
    }
