from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json
import os


DEFAULT_STATE_URL = "http://127.0.0.1:4000/api/v1/state"
STATE_URL_ENV = "MINI_ORCHESTRATOR_DAEMON_STATE_URL"


class SymphonyDaemonError(RuntimeError):
    pass


def configured_state_url() -> str:
    return os.environ.get(STATE_URL_ENV, DEFAULT_STATE_URL).strip()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_symphony_state(url: str, timeout: float = 2.0) -> Dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            payload = json.loads(response.read().decode(charset))
    except HTTPError as exc:
        raise SymphonyDaemonError(f"Symphony daemon returned HTTP {exc.code}.") from exc
    except URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise SymphonyDaemonError(f"Symphony daemon is unavailable: {reason}") from exc
    except TimeoutError as exc:
        raise SymphonyDaemonError("Symphony daemon request timed out.") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise SymphonyDaemonError(f"Symphony daemon state could not be read: {exc}") from exc

    if not isinstance(payload, dict):
        raise SymphonyDaemonError("Symphony daemon state response was not a JSON object.")
    if isinstance(payload.get("error"), dict):
        message = str(payload["error"].get("message") or payload["error"].get("code") or "unknown error")
        raise SymphonyDaemonError(f"Symphony daemon state error: {message}")
    return payload


def _text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    return str(value)


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _entry_id(entry: Dict[str, Any], prefix: str) -> str:
    return (
        _text(entry.get("issue_identifier"))
        or _text(entry.get("issue_id"))
        or f"{prefix}-unknown"
    )


def _entry_title(entry: Dict[str, Any]) -> str:
    identifier = _text(entry.get("issue_identifier"))
    state = _text(entry.get("state"))
    if identifier and state:
        return f"{identifier} - {state}"
    return identifier or _text(entry.get("issue_id"), "Symphony task")


def _tokens(entry: Dict[str, Any]) -> Dict[str, int]:
    raw = entry.get("tokens") if isinstance(entry.get("tokens"), dict) else {}
    return {
        "input": _int(raw.get("input_tokens") or raw.get("input")),
        "output": _int(raw.get("output_tokens") or raw.get("output")),
        "total": _int(raw.get("total_tokens") or raw.get("total")),
    }


def _stage(entry: Dict[str, Any], status: str) -> Dict[str, Any]:
    tokens = _tokens(entry)
    label = _text(entry.get("worker_host")) or "Symphony worker"
    last_event = _text(entry.get("last_event")) or _text(entry.get("last_message")) or _text(entry.get("error"))
    return {
        "agent": label,
        "label": label,
        "status": status,
        "statusLabel": status.replace("_", " ").title(),
        "startedAt": entry.get("started_at") or entry.get("blocked_at") or entry.get("due_at"),
        "completedAt": None,
        "threadId": entry.get("session_id"),
        "turnCount": _int(entry.get("turn_count")),
        "model": None,
        "tokens": tokens["total"],
        "lastEvent": last_event,
        "output": _text(entry.get("last_message")),
    }


def _run_from_entry(entry: Dict[str, Any], status: str, generated_at: str) -> Dict[str, Any]:
    run_id = _entry_id(entry, status)
    tokens = _tokens(entry)
    last_event = (
        _text(entry.get("last_event"))
        or _text(entry.get("last_message"))
        or _text(entry.get("error"))
        or status.replace("_", " ").title()
    )
    updated_at = (
        _text(entry.get("last_event_at"))
        or _text(entry.get("blocked_at"))
        or _text(entry.get("due_at"))
        or _text(entry.get("started_at"))
        or generated_at
    )
    return {
        "schemaVersion": 1,
        "runId": run_id,
        "sourceKey": "symphony",
        "sourceLabel": "Symphony",
        "status": status,
        "mode": "symphony-daemon",
        "currentAgent": _text(entry.get("worker_host")) or "Symphony worker",
        "task": {
            "taskId": _text(entry.get("issue_id")) or run_id,
            "title": _entry_title(entry),
            "raw": _text(entry.get("issue_url")) or _text(entry.get("issue_id")) or run_id,
        },
        "profileSnapshotId": "symphony-daemon",
        "workspacePath": _text(entry.get("workspace_path")),
        "thread": {
            "threadId": entry.get("session_id"),
            "currentTurnId": None,
            "turnCount": _int(entry.get("turn_count")),
            "workers": [],
        },
        "tokens": tokens,
        "artifacts": {
            "eventLogPath": _text(entry.get("issue_url")),
            "workspaceGenerated": bool(entry.get("workspace_path")),
            "durableProjectMemory": False,
            "privateRuntimeData": True,
        },
        "lastEvent": last_event,
        "lastError": _text(entry.get("error")) if status in {"blocked", "retrying"} else "",
        "approval": {"required": status == "blocked", "count": 1 if status == "blocked" else 0},
        "chainPreset": {},
        "stages": [_stage(entry, status)],
        "eventTypes": {},
        "createdAt": _text(entry.get("started_at")) or generated_at,
        "updatedAt": updated_at,
        "reviewerVerdict": None,
        "stale": {
            "isStale": False,
            "reason": "",
            "lastEventAt": updated_at,
            "thresholdSeconds": 0,
        },
        "outputs": {},
    }


def build_symphony_live_runs(state: Dict[str, Any], state_url: str) -> Dict[str, Any]:
    generated_at = _text(state.get("generated_at")) or _utc_now()
    runs: list[Dict[str, Any]] = []

    for status in ("running", "retrying", "blocked"):
        entries = state.get(status)
        if not isinstance(entries, list):
            entries = []
        for entry in entries:
            if isinstance(entry, dict):
                runs.append(_run_from_entry(entry, status, generated_at))

    summary = {
        "total": len(runs),
        "active": sum(1 for run in runs if run["status"] in {"running", "retrying"}),
        "blocked": sum(1 for run in runs if run["status"] == "blocked"),
        "done": 0,
        "failed": 0,
    }
    profiles = {
        "symphony-daemon": {
            "displayName": "Symphony Daemon",
            "role": "daemon",
            "model": "-",
        }
    }
    return {
        "source": "symphony-daemon",
        "stateUrl": state_url,
        "generatedAt": generated_at,
        "summary": summary,
        "profiles": profiles,
        "runs": runs,
        "codexTotals": state.get("codex_totals") if isinstance(state.get("codex_totals"), dict) else {},
        "rateLimits": state.get("rate_limits"),
    }


def build_symphony_live_runs_from_url(url: str | None = None, timeout: float = 2.0) -> Dict[str, Any]:
    state_url = (url or configured_state_url()).strip()
    state = fetch_symphony_state(state_url, timeout=timeout)
    return build_symphony_live_runs(state, state_url)
