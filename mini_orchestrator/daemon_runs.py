from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from . import runtime_store
from .model_defaults import (
    DEFAULT_COORDINATOR_MODEL,
    DEFAULT_VISUAL_AGENT_MODEL,
    DEFAULT_VISUAL_TRANSLATION_MODEL,
)


LOCAL_DAEMON_RUN_DIR = ".mini_orchestrator/daemon-runs"
REVIEW_DECISIONS = {"done", "rework"}


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
        "sourceKey": "dispatcher",
        "sourceLabel": "Dispatcher",
        "task": {
            "taskId": task_id,
            "sprintId": sprint_id,
            "project": "mini-orchestrator",
        },
        "profileSnapshotId": profile_snapshot_id,
        "status": status,
        "currentAgent": profile_snapshot_id,
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
        "stages": [
            {
                "agent": profile_snapshot_id,
                "label": profile_snapshot_id,
                "status": status,
                "statusLabel": status.replace("_", " ").title(),
                "startedAt": created_at,
                "completedAt": updated_at if status in {"done", "review"} else None,
                "threadId": thread_id,
                "turnCount": turn_count,
                "model": None,
                "tokens": total_tokens,
                "lastEvent": last_event,
                "output": "",
            }
        ],
        "outputs": {},
        "review": {
            "decision": "",
            "decidedAt": "",
        },
        "reviewerVerdict": None,
        "stale": {
            "isStale": False,
            "reason": "",
            "lastEventAt": updated_at,
            "thresholdSeconds": 0,
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
            "model": DEFAULT_COORDINATOR_MODEL,
        },
        "profile-executor-demo": {
            "displayName": "Executor Demo",
            "role": "Executor",
            "model": DEFAULT_VISUAL_AGENT_MODEL,
        },
        "profile-reviewer-demo": {
            "displayName": "Reviewer Demo",
            "role": "Reviewer",
            "model": DEFAULT_VISUAL_TRANSLATION_MODEL,
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


def run_single_card_dry_run(
    manifest: dict[str, Any],
    profile_snapshot_id: str,
    root: Path,
    *,
    task: dict[str, str] | None = None,
) -> Dict[str, Any]:
    profiles = manifest.get("profileSnapshots") if isinstance(manifest.get("profileSnapshots"), list) else []
    profile = next((item for item in profiles if item.get("snapshotId") == profile_snapshot_id), None)
    if not isinstance(profile, dict):
        raise ValueError(f"Profile snapshot was not found in manifest: {profile_snapshot_id}")
    if len(profiles) != 1:
        raise ValueError("Single-card daemon MVP requires a manifest with exactly one profile snapshot.")

    run_id = f"daemon-{uuid.uuid4().hex[:12]}"
    created_at = _utc_now()
    event_log = runtime_store.runtime_uri("daemon-runs", f"{run_id}/events")
    workspace_path = f".mini_orchestrator/generated-workspaces/{run_id}"
    state = _run_state(
        run_id=run_id,
        task_id=str((task or {}).get("taskId") or manifest.get("manifestId") or run_id),
        sprint_id=str((task or {}).get("sprintId") or "local-daemon-dry-run"),
        profile_snapshot_id=profile_snapshot_id,
        status="queued",
        workspace_path=workspace_path,
        thread_id=None,
        turn_id=None,
        turn_count=0,
        input_tokens=0,
        output_tokens=0,
        last_event="queued",
        last_error=None,
        event_log_path=event_log,
        created_at=created_at,
        updated_at=created_at,
    )
    _append_event(root, run_id, {"time": created_at, "type": "queued", "runId": run_id, "manifestId": manifest.get("manifestId")})

    for status, event_type in (("claimed", "workspace_prepared"), ("running", "dry_run_started")):
        now = _utc_now()
        state["status"] = status
        state["lastEvent"] = event_type
        state["updatedAt"] = now
        _append_event(root, run_id, {"time": now, "type": event_type, "runId": run_id, "profileSnapshotId": profile_snapshot_id})

    output_text = f"Dry-run completed for {profile.get('displayName') or profile_snapshot_id}."
    done_at = _utc_now()
    state["status"] = "review"
    state["currentAgent"] = profile_snapshot_id
    state["thread"] = {"threadId": f"dry-run-{run_id}", "currentTurnId": f"turn-{run_id}", "turnCount": 1}
    state["tokens"] = {"input": 0, "output": 0, "total": 0}
    state["lastEvent"] = "ready_for_human_review"
    state["updatedAt"] = done_at
    state["output"] = output_text
    state["outputs"] = {profile_snapshot_id: output_text}
    state["stages"][0]["status"] = "done"
    state["stages"][0]["statusLabel"] = "Done"
    state["stages"][0]["completedAt"] = done_at
    state["stages"][0]["threadId"] = f"dry-run-{run_id}"
    state["stages"][0]["turnCount"] = 1
    state["stages"][0]["lastEvent"] = "dry_run_completed"
    state["stages"][0]["output"] = output_text
    _append_event(
        root,
        run_id,
        {
            "time": done_at,
            "type": "ready_for_human_review",
            "runId": run_id,
            "profileSnapshotId": profile_snapshot_id,
            "output": output_text,
        },
    )
    _write_state(root, state)
    return state


def run_manifest_dry_run(
    manifest: dict[str, Any],
    root: Path,
    *,
    task: dict[str, str] | None = None,
    reviewer_verdict: str = "done",
) -> Dict[str, Any]:
    profiles = manifest.get("profileSnapshots") if isinstance(manifest.get("profileSnapshots"), list) else []
    if not profiles:
        raise ValueError("Run manifest has no profile snapshots.")
    graph = manifest.get("graph") if isinstance(manifest.get("graph"), dict) else {}
    execution_order = graph.get("executionOrder") if isinstance(graph.get("executionOrder"), list) else []
    if not execution_order:
        execution_order = [str(profile.get("source", {}).get("sourceCardId") or "") for profile in profiles]
    profile_by_card_id = {
        str(profile.get("source", {}).get("sourceCardId") or ""): profile
        for profile in profiles
        if isinstance(profile, dict)
    }
    ordered_profiles = [profile_by_card_id[card_id] for card_id in execution_order if card_id in profile_by_card_id]
    if len(ordered_profiles) != len(profiles):
        raise ValueError("Run manifest graph does not cover every profile snapshot.")

    run_id = f"daemon-{uuid.uuid4().hex[:12]}"
    created_at = _utc_now()
    event_log = runtime_store.runtime_uri("daemon-runs", f"{run_id}/events")
    workspace_path = f".mini_orchestrator/generated-workspaces/{run_id}"
    state = _run_state(
        run_id=run_id,
        task_id=str((task or {}).get("taskId") or manifest.get("manifestId") or run_id),
        sprint_id=str((task or {}).get("sprintId") or "local-daemon-dry-run"),
        profile_snapshot_id=str(ordered_profiles[0].get("snapshotId") or manifest.get("manifestId") or run_id),
        status="queued",
        workspace_path=workspace_path,
        thread_id=None,
        turn_id=None,
        turn_count=0,
        input_tokens=0,
        output_tokens=0,
        last_event="queued",
        last_error=None,
        event_log_path=event_log,
        created_at=created_at,
        updated_at=created_at,
    )
    state["manifestId"] = manifest.get("manifestId")
    state["nodeStates"] = []
    state["flowArtifacts"] = []
    _append_event(root, run_id, {"time": created_at, "type": "queued", "runId": run_id, "manifestId": manifest.get("manifestId")})

    previous_artifacts: list[dict[str, str]] = []
    for index, profile in enumerate(ordered_profiles):
        node_id = str(profile.get("source", {}).get("sourceCardId") or profile.get("snapshotId") or f"node-{index + 1}")
        snapshot_id = str(profile.get("snapshotId") or node_id)
        role = str(profile.get("role") or "")
        now = _utc_now()
        state["status"] = "running"
        state["currentAgent"] = node_id
        state["lastEvent"] = f"{node_id}: started"
        state["updatedAt"] = now
        state["nodeStates"].append(
            {
                "agentId": node_id,
                "snapshotId": snapshot_id,
                "role": role,
                "status": "running",
                "startedAt": now,
                "completedAt": None,
            }
        )
        _append_event(
            root,
            run_id,
            {
                "time": now,
                "type": "node_started",
                "runId": run_id,
                "agentId": node_id,
                "snapshotId": snapshot_id,
                "inputArtifacts": previous_artifacts,
            },
        )
        output = _simulated_node_output(profile, previous_artifacts, reviewer_verdict if role == "Reviewer" else "")
        artifact = {
            "artifactId": f"artifact-{node_id}",
            "agentId": node_id,
            "role": role,
            "summary": output["summary"],
        }
        if output.get("verdict"):
            artifact["verdict"] = output["verdict"]
        previous_artifacts = [*previous_artifacts, artifact]
        done_at = _utc_now()
        state["nodeStates"][-1]["status"] = "done"
        state["nodeStates"][-1]["completedAt"] = done_at
        state["flowArtifacts"] = previous_artifacts
        state["lastEvent"] = f"{node_id}: completed"
        state["updatedAt"] = done_at
        _append_event(
            root,
            run_id,
            {
                "time": done_at,
                "type": "node_completed",
                "runId": run_id,
                "agentId": node_id,
                "snapshotId": snapshot_id,
                "artifact": artifact,
            },
        )

    final_verdict = _normalize_verdict(previous_artifacts[-1].get("verdict", "done") if previous_artifacts else "done")
    final_status = {
        "done": "review",
        "needs_changes": "retrying",
        "blocked": "blocked",
        "failed": "failed",
    }[final_verdict]
    completed_at = _utc_now()
    state["status"] = final_status
    state["currentAgent"] = str(ordered_profiles[-1].get("source", {}).get("sourceCardId") or ordered_profiles[-1].get("snapshotId") or "")
    if state.get("nodeStates") and final_status != "done":
        state["nodeStates"][-1]["status"] = final_status
    state["thread"] = {"threadId": f"dry-run-{run_id}", "currentTurnId": f"turn-{run_id}", "turnCount": len(ordered_profiles)}
    state["lastEvent"] = "ready_for_human_review" if final_status == "review" else f"reviewer verdict: {final_verdict}"
    state["lastError"] = "Reviewer blocked the run." if final_status == "blocked" else None
    state["reviewerVerdict"] = final_verdict
    state["updatedAt"] = completed_at
    _append_event(
        root,
        run_id,
        {
            "time": completed_at,
            "type": "ready_for_human_review" if final_status == "review" else "run_completed",
            "runId": run_id,
            "status": final_status,
            "reviewerVerdict": final_verdict,
        },
    )
    _write_state(root, state)
    return state


def build_local_daemon_runs(root: Path) -> Dict[str, Any]:
    runs: list[dict[str, Any]] = runtime_store.list_json_documents(root, "daemon_runs")
    seen = {str(run.get("runId") or "") for run in runs}
    run_dir = root / LOCAL_DAEMON_RUN_DIR
    if run_dir.exists():
        for path in sorted(run_dir.glob("*.state.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict) and str(data.get("runId") or "") not in seen:
                runs.append(data)
    profiles = {
        str(run.get("profileSnapshotId")): {
            "displayName": str(run.get("profileSnapshotId") or "Daemon profile"),
            "role": "visual-agent",
            "model": "dry-run",
        }
        for run in runs
    }
    active_statuses = {"queued", "claimed", "running", "blocked", "retrying"}
    return {
        "service": "mini-orchestrator",
        "source": "mini-daemon-jsonl",
        "generatedAt": _utc_now(),
        "summary": {
            "total": len(runs),
            "active": sum(1 for run in runs if run.get("status") in active_statuses),
            "blocked": sum(1 for run in runs if run.get("status") == "blocked"),
            "done": sum(1 for run in runs if run.get("status") == "done"),
            "failed": sum(1 for run in runs if run.get("status") == "failed"),
            "review": sum(1 for run in runs if run.get("status") == "review"),
        },
        "profiles": profiles,
        "runs": runs,
    }


def _write_state(root: Path, state: dict[str, Any]) -> None:
    runtime_store.upsert_json_document(root, "daemon_runs", str(state["runId"]), state)


def set_run_review_decision(run_id: str, decision: str, root: Path) -> dict[str, Any]:
    normalized_run_id = str(run_id or "").strip()
    normalized_decision = str(decision or "").strip().casefold()
    if not normalized_run_id:
        raise ValueError("Field 'runId' is required.")
    if normalized_decision not in REVIEW_DECISIONS:
        raise ValueError("Field 'decision' must be 'done' or 'rework'.")

    state = runtime_store.get_json_document(root, "daemon_runs", normalized_run_id)
    path = root / LOCAL_DAEMON_RUN_DIR / f"{normalized_run_id}.state.json"
    if state is None and path.exists():
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Daemon run state is not valid JSON: {normalized_run_id}") from exc
    if state is None:
        raise ValueError(f"Daemon run state was not found: {normalized_run_id}")
    if not isinstance(state, dict):
        raise ValueError(f"Daemon run state is not an object: {normalized_run_id}")

    decided_at = _utc_now()
    state["review"] = {"decision": normalized_decision, "decidedAt": decided_at}
    state["updatedAt"] = decided_at
    state.setdefault("stale", {})
    if isinstance(state["stale"], dict):
        state["stale"]["lastEventAt"] = decided_at

    if normalized_decision == "done":
        state["status"] = "done"
        state["lastEvent"] = "user accepted result"
    else:
        state["status"] = "review"
        state["lastEvent"] = "user requested rework"

    _append_event(
        root,
        normalized_run_id,
        {
            "time": decided_at,
            "type": "review_decision",
            "runId": normalized_run_id,
            "decision": normalized_decision,
            "status": state["status"],
        },
    )
    _write_state(root, state)
    return state


def _append_event(root: Path, run_id: str, event: dict[str, Any]) -> None:
    runtime_store.insert_daemon_event(root, run_id, event)


def _simulated_node_output(profile: dict[str, Any], previous_artifacts: list[dict[str, str]], verdict: str) -> dict[str, str]:
    role = str(profile.get("role") or "Agent")
    display_name = str(profile.get("displayName") or role)
    summary = f"{display_name} dry-run output"
    if previous_artifacts:
        summary += f" after {len(previous_artifacts)} artifact(s)"
    result = {"summary": summary}
    if verdict:
        result["verdict"] = _normalize_verdict(verdict)
    return result


def _normalize_verdict(value: str) -> str:
    normalized = str(value or "done").strip().lower().replace("-", "_")
    if normalized in {"done", "needs_changes", "blocked", "failed"}:
        return normalized
    return "failed"


def _project_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
