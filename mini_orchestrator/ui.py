from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Any, Dict
import json
import os
import subprocess
import sys
import threading
import uuid
import time
import webbrowser
from urllib.parse import parse_qs, unquote, urlparse

from .agent_flows import (
    AgentFlowError,
    compile_saved_agent_flow,
    create_agent_flow,
    list_agent_flows,
    read_compiled_manifest,
    read_agent_flow,
    update_agent_flow,
    validate_saved_agent_flow,
)
from .agent_api import AgentApiError, VisualAgentApi
from .agent_profiles import (
    AgentProfileError,
    DEFAULT_PROJECT_BUILDER_TASK,
    compile_worker_profile,
    default_project_builder_agent_card,
    load_or_create_default_agent_card,
    persist_agent_card,
    visual_agent_task_prompt,
)
from .codex_dispatcher_service import PersistentCodexDispatcher
from .daemon_runs import build_local_daemon_runs, run_manifest_dry_run, run_single_card_dry_run, set_run_review_decision
from .live_runs import build_dispatcher_live_runs
from .orchestrator import Orchestrator
from . import runtime_store
from .symphony_daemon import (
    SymphonyDaemonError,
    build_local_symphony_gateway_runs,
    build_symphony_live_runs_from_url,
    create_symphony_gateway_run,
    fetch_symphony_issue,
    refresh_symphony_state,
)
from .symphony_gateway import SymphonyGateway
from .worknest_bridge import WorkNestBridgeError, WorkNestLifecycleBridge


ROOT = Path(__file__).resolve().parents[1]
DISPATCHER = ROOT / "tools" / "codex-dispatcher" / "dispatcher.py"
MAX_TECH_EVENTS = 80
MAX_TECH_LOG_LINES = 5000
LIVE_RUN_SOURCE_MODES = {"dispatcher", "symphony", "combined"}
APPROVED_WORKFLOW_TURN_TIMEOUT_SECONDS = 300


def _empty_run_summary() -> Dict[str, int]:
    return {"total": 0, "active": 0, "blocked": 0, "done": 0, "failed": 0, "stale": 0}


def _merge_run_summaries(payloads: list[Dict[str, Any]]) -> Dict[str, int]:
    summary = _empty_run_summary()
    for payload in payloads:
        payload_summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        for key in summary:
            summary[key] += int(payload_summary.get(key) or 0)
    return summary


def _stamp_run_source(payload: Dict[str, Any], source_key: str, source_label: str) -> Dict[str, Any]:
    for run in payload.get("runs") if isinstance(payload.get("runs"), list) else []:
        if isinstance(run, dict):
            run["sourceKey"] = source_key
            run["sourceLabel"] = source_label
    return payload


def _string_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _symphony_agent_models_from_gateway_run(run: Dict[str, Any]) -> Dict[str, str]:
    symphony = run.get("symphony") if isinstance(run.get("symphony"), dict) else {}
    submission = symphony.get("submission") if isinstance(symphony.get("submission"), dict) else {}
    intake = symphony.get("intakePayload") if isinstance(symphony.get("intakePayload"), dict) else submission.get("request")
    agent_tasks = intake.get("agentTasks") if isinstance(intake, dict) and isinstance(intake.get("agentTasks"), list) else []
    models: Dict[str, str] = {}
    for index, agent_task in enumerate(agent_tasks):
        if not isinstance(agent_task, dict):
            continue
        agent = agent_task.get("agent") if isinstance(agent_task.get("agent"), dict) else {}
        codex = agent_task.get("codex") if isinstance(agent_task.get("codex"), dict) else {}
        agent_id = _string_value(agent.get("id") or agent_task.get("agentId") or agent_task.get("stageId"))
        model = _string_value(codex.get("model") or agent_task.get("model"))
        if model:
            if agent_id:
                models[agent_id] = model
            models[str(index)] = model
    return models


def _symphony_model_index_from_gateway_payload(gateway_payload: Dict[str, Any]) -> Dict[str, str]:
    index: Dict[str, str] = {}
    runs = gateway_payload.get("runs") if isinstance(gateway_payload.get("runs"), list) else []
    for run in runs:
        if not isinstance(run, dict):
            continue
        agent_models = _symphony_agent_models_from_gateway_run(run)
        symphony = run.get("symphony") if isinstance(run.get("symphony"), dict) else {}
        chain = symphony.get("miniOwnedChain") if isinstance(symphony.get("miniOwnedChain"), dict) else {}
        outputs = chain.get("outputs") if isinstance(chain.get("outputs"), list) else []
        for output in outputs:
            if not isinstance(output, dict):
                continue
            agent_id = _string_value(output.get("agentId"))
            model = agent_models.get(agent_id) or agent_models.get(_string_value(output.get("agentIndex")))
            if not model:
                continue
            issues = output.get("issues") if isinstance(output.get("issues"), list) else []
            for issue in issues:
                if isinstance(issue, dict):
                    for key in (issue.get("issue_identifier"), issue.get("identifier"), issue.get("issue_id")):
                        key_text = _string_value(key)
                        if key_text:
                            index[key_text] = model

        submission = symphony.get("submission") if isinstance(symphony.get("submission"), dict) else {}
        response = submission.get("response") if isinstance(submission.get("response"), dict) else {}
        accepted = response.get("accepted") if isinstance(response.get("accepted"), list) else []
        for position, issue in enumerate(accepted):
            if not isinstance(issue, dict):
                continue
            model = agent_models.get(str(position))
            if not model:
                continue
            for key in (issue.get("issue_identifier"), issue.get("identifier"), issue.get("issue_id")):
                key_text = _string_value(key)
                if key_text:
                    index[key_text] = model
    return index


def _enrich_symphony_daemon_models(daemon_payload: Dict[str, Any], gateway_payload: Dict[str, Any]) -> Dict[str, Any]:
    model_index = _symphony_model_index_from_gateway_payload(gateway_payload)
    if not model_index:
        return daemon_payload
    runs = daemon_payload.get("runs") if isinstance(daemon_payload.get("runs"), list) else []
    for run in runs:
        if not isinstance(run, dict) or run.get("mode") == "symphony-daemon-summary":
            continue
        task = run.get("task") if isinstance(run.get("task"), dict) else {}
        keys = [
            _string_value(run.get("runId")),
            _string_value(task.get("taskId")),
            _string_value(task.get("raw")),
        ]
        model = next((model_index[key] for key in keys if key in model_index), "")
        if not model:
            continue
        run["model"] = model
        for stage in run.get("stages") if isinstance(run.get("stages"), list) else []:
            if isinstance(stage, dict) and not stage.get("model"):
                stage["model"] = model
    return daemon_payload


def _build_dispatcher_source_payload(root: Path) -> Dict[str, Any]:
    local_payload = build_local_daemon_runs(root)
    dispatcher_payload = build_dispatcher_live_runs(root)
    _stamp_run_source(local_payload, "dispatcher", "Dispatcher")
    _stamp_run_source(dispatcher_payload, "dispatcher", "Dispatcher")

    payloads = [local_payload, dispatcher_payload]
    runs = [
        run
        for payload in payloads
        for run in (payload.get("runs") if isinstance(payload.get("runs"), list) else [])
        if isinstance(run, dict)
    ]
    profiles: Dict[str, Any] = {}
    for payload in payloads:
        payload_profiles = payload.get("profiles")
        if isinstance(payload_profiles, dict):
            profiles.update(payload_profiles)
    runs.sort(key=lambda run: str(run.get("updatedAt") or run.get("createdAt") or ""), reverse=True)
    return {
        "source": "dispatcher",
        "sourceLabel": "Dispatcher",
        "generatedAt": max(str(payload.get("generatedAt") or "") for payload in payloads),
        "summary": _merge_run_summaries(payloads),
        "profiles": profiles,
        "runs": runs,
        "sourceDetails": {
            "localDaemon": {
                "source": local_payload.get("source"),
                "summary": local_payload.get("summary") or _empty_run_summary(),
            },
            "dispatcherJsonl": {
                "source": dispatcher_payload.get("source"),
                "summary": dispatcher_payload.get("summary") or _empty_run_summary(),
            },
        },
    }


def _build_symphony_source_payload(root: Path = ROOT) -> Dict[str, Any]:
    daemon_payload = build_symphony_live_runs_from_url()
    gateway_payload = build_local_symphony_gateway_runs(root)
    _enrich_symphony_daemon_models(daemon_payload, gateway_payload)
    _stamp_run_source(daemon_payload, "symphony", "Symphony")
    _stamp_run_source(gateway_payload, "symphony", "Symphony")

    payloads = [daemon_payload, gateway_payload]
    runs = [
        run
        for payload in payloads
        for run in (payload.get("runs") if isinstance(payload.get("runs"), list) else [])
        if isinstance(run, dict)
    ]
    profiles: Dict[str, Any] = {}
    for payload in payloads:
        payload_profiles = payload.get("profiles")
        if isinstance(payload_profiles, dict):
            profiles.update(payload_profiles)
    runs.sort(key=lambda run: str(run.get("updatedAt") or run.get("createdAt") or ""), reverse=True)
    return {
        "source": "symphony",
        "sourceLabel": "Symphony",
        "generatedAt": max(str(payload.get("generatedAt") or "") for payload in payloads),
        "summary": _merge_run_summaries(payloads),
        "profiles": profiles,
        "runs": runs,
        "sourceDetails": {
            "symphonyDaemon": {
                "source": daemon_payload.get("source"),
                "summary": daemon_payload.get("summary") or _empty_run_summary(),
                "stateUrl": daemon_payload.get("stateUrl"),
                "codexTotals": daemon_payload.get("codexTotals") or {},
                "rateLimits": daemon_payload.get("rateLimits"),
            },
            "symphonyGateway": {
                "source": gateway_payload.get("source"),
                "summary": gateway_payload.get("summary") or _empty_run_summary(),
            },
        },
    }


def _source_state(payload: Dict[str, Any] | None, error: str = "") -> Dict[str, Any]:
    summary = payload.get("summary") if payload and isinstance(payload.get("summary"), dict) else _empty_run_summary()
    return {
        "source": payload.get("source") if payload else None,
        "summary": summary,
        "available": not error,
        "error": error,
    }


def _combined_live_runs_payload(
    dispatcher_payload: Dict[str, Any],
    symphony_payload: Dict[str, Any] | None,
    symphony_error: str = "",
) -> Dict[str, Any]:
    payloads = [dispatcher_payload]
    if symphony_payload:
        payloads.append(symphony_payload)
    runs = [
        run
        for payload in payloads
        for run in (payload.get("runs") if isinstance(payload.get("runs"), list) else [])
        if isinstance(run, dict)
    ]
    profiles: Dict[str, Any] = {}
    for payload in payloads:
        payload_profiles = payload.get("profiles")
        if isinstance(payload_profiles, dict):
            profiles.update(payload_profiles)
    runs.sort(key=lambda run: str(run.get("updatedAt") or run.get("createdAt") or ""), reverse=True)
    generated_at = max(str(payload.get("generatedAt") or "") for payload in payloads)
    return {
        "source": "combined",
        "sourceMode": "combined",
        "sourceLabel": "Combined",
        "generatedAt": generated_at,
        "summary": _merge_run_summaries(payloads),
        "profiles": profiles,
        "runs": runs,
        "sources": {
            "dispatcher": _source_state(dispatcher_payload),
            "symphony": _source_state(symphony_payload, symphony_error),
        },
        "daemonError": symphony_error,
        "daemonSourceTried": "symphony-daemon" if symphony_error else "",
    }


def build_live_runs_payload(root: Path = ROOT, source_mode: str = "combined") -> Dict[str, Any]:
    mode = source_mode if source_mode in LIVE_RUN_SOURCE_MODES else "combined"
    dispatcher_payload = _build_dispatcher_source_payload(root)

    if mode == "dispatcher":
        dispatcher_payload["sourceMode"] = "dispatcher"
        dispatcher_payload["sources"] = {"dispatcher": _source_state(dispatcher_payload)}
        return dispatcher_payload

    try:
        symphony_payload: Dict[str, Any] | None = _build_symphony_source_payload(root)
        symphony_error = ""
    except SymphonyDaemonError as exc:
        symphony_payload = None
        symphony_error = str(exc)

    if mode == "symphony":
        if symphony_payload is None:
            return {
                "source": "symphony-daemon",
                "sourceMode": "symphony",
                "sourceLabel": "Symphony",
                "generatedAt": datetime.now(timezone.utc).isoformat(),
                "summary": _empty_run_summary(),
                "profiles": {},
                "runs": [],
                "sources": {"symphony": _source_state(None, symphony_error)},
                "daemonError": symphony_error,
                "daemonSourceTried": "symphony-daemon",
            }
        symphony_payload["sourceMode"] = "symphony"
        symphony_payload["sources"] = {"symphony": _source_state(symphony_payload)}
        return symphony_payload

    return _combined_live_runs_payload(dispatcher_payload, symphony_payload, symphony_error)


def build_symphony_run_blocker(payload: Dict[str, Any]) -> Dict[str, Any]:
    if payload.get("approved") is not True:
        raise ValueError("Field 'approved' must be true before creating a Symphony run.")
    task_value = payload.get("task")
    if isinstance(task_value, dict):
        task_title = str(task_value.get("title") or task_value.get("summary") or task_value.get("task") or "").strip()
        task_id = str(task_value.get("taskId") or "").strip()
        sprint_id = str(task_value.get("sprintId") or "").strip()
    else:
        task_title = str(task_value or payload.get("goal") or "").strip()
        task_id = str(payload.get("taskId") or "").strip()
        sprint_id = str(payload.get("sprintId") or "").strip()
    if not task_title:
        raise ValueError("Field 'task' is required.")

    return {
        "status": "blocked",
        "accepted": False,
        "code": "symphony-intake-missing",
        "message": (
            "Symphony intake is not documented for external mini-orchestrator task runs yet. "
            "Use dispatcher execution or add a config-service-resolved Symphony intake contract first."
        ),
        "task": {
            "taskId": task_id,
            "sprintId": sprint_id,
            "project": str(payload.get("project") or "mini-orchestrator").strip(),
            "title": task_title,
        },
        "requiredContract": {
            "serviceId": "symphony",
            "expectedCapability": "task-intake",
            "expectedEndpoint": "documented agent-facing intake endpoint",
        },
    }


@dataclass
class UiConfig:
    host: str
    port: int
    open_browser: bool
    service_id: str = "mini-orchestrator"
    base_url: str = ""


def _resolve_dispatcher_log_path(root: Path, log_value: str) -> Path | None:
    if not log_value:
        return None
    raw_path = Path(log_value)
    log_path = raw_path if raw_path.is_absolute() else root / raw_path
    try:
        resolved = log_path.resolve()
        resolved.relative_to(root.resolve())
    except (OSError, ValueError):
        return None
    return resolved


def _compact_dispatcher_event(event: Dict[str, Any]) -> Dict[str, Any]:
    compact: Dict[str, Any] = {}
    for key in (
        "time",
        "type",
        "agent",
        "model",
        "threadId",
        "turnId",
        "reused",
        "name",
        "elapsedSeconds",
        "to",
        "role",
        "reason",
        "confidence",
        "dryRun",
        "chain",
        "planOnly",
        "targetWorkspace",
        "workerChatRoot",
        "processCwd",
    ):
        if key in event:
            compact[key] = event[key]

    if "prompt" in event:
        compact["promptChars"] = len(str(event.get("prompt") or ""))
    if "output" in event:
        compact["outputChars"] = len(str(event.get("output") or ""))

    if event.get("type") == "codex_notification":
        message = event.get("message")
        if isinstance(message, dict):
            method = message.get("method")
            if method:
                compact["method"] = method
            if "id" in message:
                compact["id"] = message.get("id")
            params = message.get("params")
            if isinstance(params, dict):
                item = params.get("item")
                if isinstance(item, dict) and item.get("type"):
                    compact["itemType"] = item.get("type")
                turn = params.get("turn")
                if isinstance(turn, dict) and turn.get("id"):
                    compact["turnId"] = turn.get("id")
    return compact


def build_dispatcher_tech_summary(result: Dict[str, Any], root: Path = ROOT) -> Dict[str, Any]:
    log_value = str(result.get("log") or "").strip()
    tech: Dict[str, Any] = {
        "runtime": result.get("runtime") or "dispatcher-subprocess",
        "mode": result.get("mode"),
        "previewMode": result.get("previewMode"),
        "planOnly": result.get("planOnly"),
        "durationSeconds": result.get("durationSeconds"),
        "log": log_value or None,
        "targetWorkspace": result.get("targetWorkspace"),
        "workerChatRoot": result.get("workerChatRoot"),
        "processCwd": result.get("processCwd"),
        "logStatus": "not-provided",
        "workerVisibility": (
            "dry-run-no-codex-worker" if result.get("previewMode") == "dry-run" else "unknown"
        ),
        "dispatchDecision": result.get("dispatchDecision"),
        "eventTypes": {},
        "workers": [],
        "turns": [],
        "timings": [],
        "codexNotifications": {},
        "recentEvents": [],
    }
    log_path = _resolve_dispatcher_log_path(root, log_value)
    if log_path is None:
        return tech
    if not log_path.exists():
        tech["logStatus"] = "missing"
        return tech

    tech["logStatus"] = "available"
    workers_by_thread: dict[str, Dict[str, Any]] = {}
    recent_events: list[Dict[str, Any]] = []
    line_count = 0
    truncated = False

    with log_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line_count += 1
            if line_count > MAX_TECH_LOG_LINES:
                truncated = True
                break
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue

            event_type = str(event.get("type") or "unknown")
            event_types = tech["eventTypes"]
            event_types[event_type] = int(event_types.get(event_type, 0)) + 1
            compact = _compact_dispatcher_event(event)
            recent_events.append(compact)
            if len(recent_events) > MAX_TECH_EVENTS:
                recent_events.pop(0)

            if event.get("time"):
                tech["lastEventTime"] = event.get("time")

            if event_type == "app_server_started":
                tech["runtime"] = "codex-app-server"
                tech["workerVisibility"] = "codex-sidebar-visible"
                tech["targetWorkspace"] = event.get("targetWorkspace")
                tech["workerChatRoot"] = event.get("workerChatRoot")
                tech["processCwd"] = event.get("processCwd")
            elif event_type == "task_created" and event.get("dryRun") is True:
                tech["workerVisibility"] = "dry-run-no-codex-worker"
            elif event_type == "agent_thread_started":
                if event.get("targetWorkspace"):
                    tech["targetWorkspace"] = event.get("targetWorkspace")
                if event.get("workerChatRoot"):
                    tech["workerChatRoot"] = event.get("workerChatRoot")
                    tech["workerVisibility"] = "codex-sidebar-visible"
                thread_id = str(event.get("threadId") or "")
                worker = {
                    "agent": event.get("agent"),
                    "model": event.get("model"),
                    "threadId": thread_id or None,
                    "reused": bool(event.get("reused")),
                    "workerChatRoot": event.get("workerChatRoot"),
                    "turnIds": [],
                }
                tech["workers"].append(worker)
                if thread_id:
                    workers_by_thread[thread_id] = worker
            elif event_type == "agent_turn_started":
                turn = {
                    "agent": event.get("agent"),
                    "threadId": event.get("threadId"),
                    "turnId": event.get("turnId"),
                }
                tech["turns"].append(turn)
                thread_id = str(event.get("threadId") or "")
                worker = workers_by_thread.get(thread_id)
                if worker and event.get("turnId"):
                    worker.setdefault("turnIds", []).append(event.get("turnId"))
            elif event_type == "timing":
                tech["timings"].append(
                    {
                        "name": event.get("name"),
                        "agent": event.get("agent"),
                        "elapsedSeconds": event.get("elapsedSeconds"),
                    }
                )
            elif event_type == "codex_notification":
                method = compact.get("method") or "unknown"
                notifications = tech["codexNotifications"]
                notifications[method] = int(notifications.get(method, 0)) + 1

    tech["eventCount"] = line_count - (1 if truncated else 0)
    tech["truncated"] = truncated
    tech["recentEvents"] = recent_events
    return tech


class _ThreadedHttpServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class _OrchestratorUIHandler(BaseHTTPRequestHandler):
    orchestrator: Orchestrator
    dispatcher_service: PersistentCodexDispatcher
    web_root: Path
    service_id: str = "mini-orchestrator"
    dispatcher_processes: dict[str, subprocess.Popen[Any]] = {}

    def _path(self) -> str:
        return urlparse(self.path).path

    def _query(self) -> Dict[str, list[str]]:
        return parse_qs(urlparse(self.path).query)

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length).decode("utf-8", errors="replace") if length else "{}"
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON payload.") from exc
        if not isinstance(payload, dict):
            raise ValueError("Request payload must be an object.")
        return payload

    def _json_response(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _http_error(self, status: int, message: str) -> None:
        self._json_response(status, {"error": message})

    def _write_task_file(self, task: str, run_id: str | None = None) -> tuple[list[str], str | None]:
        selected_run_id = run_id or f"task-{uuid.uuid4().hex[:12]}"
        runtime_store.store_dispatcher_task(ROOT, selected_run_id, task)
        return ["--task", task], selected_run_id

    def _write_chain_preset_file(self, chain_preset: Any, run_id: str) -> list[str]:
        if not isinstance(chain_preset, dict):
            return []
        runtime_store.store_dispatcher_chain_preset(ROOT, run_id, chain_preset)
        return ["--chain-preset-id", run_id]

    def _start_dispatcher_background(self, args: list[str], run_id: str) -> Dict[str, Any]:
        if not DISPATCHER.exists():
            raise RuntimeError(f"Dispatcher script is missing: {DISPATCHER}")

        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["MINI_ORCHESTRATOR_DISPATCHER_BEST_EFFORT_LOGS"] = "1"
        creationflags = 0
        startupinfo = None
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        process = subprocess.Popen(
            [sys.executable, str(DISPATCHER), *args],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            creationflags=creationflags,
            startupinfo=startupinfo,
        )
        self.dispatcher_processes[run_id] = process
        self._capture_dispatcher_process_output(process, run_id)
        log_value = str((ROOT / "tools" / "codex-dispatcher" / "runs" / f"{run_id}.jsonl").relative_to(ROOT))
        self._write_run_metadata_event(
            run_id,
            "dispatcher_process_started",
            processId=process.pid,
            stdout=runtime_store.runtime_uri("dispatcher-processes", f"{run_id}/stdout"),
            stderr=runtime_store.runtime_uri("dispatcher-processes", f"{run_id}/stderr"),
        )
        return {
            "status": "running",
            "runId": run_id,
            "log": log_value,
            "mode": "chain",
            "planOnly": False,
            "background": True,
            "processId": process.pid,
            "stdout": runtime_store.runtime_uri("dispatcher-processes", f"{run_id}/stdout"),
            "stderr": runtime_store.runtime_uri("dispatcher-processes", f"{run_id}/stderr"),
        }

    def _capture_dispatcher_process_output(self, process: subprocess.Popen[str], run_id: str) -> None:
        def capture() -> None:
            stdout, stderr = process.communicate()
            runtime_store.store_dispatcher_process_output(ROOT, run_id, "stdout", stdout or "")
            runtime_store.store_dispatcher_process_output(ROOT, run_id, "stderr", stderr or "")

        thread = threading.Thread(target=capture, name=f"dispatcher-output-{run_id}", daemon=True)
        thread.start()

    def _write_run_metadata_event(self, run_id: str, event_type: str, **payload: Any) -> None:
        log_path = ROOT / "tools" / "codex-dispatcher" / "runs" / f"{run_id}.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "time": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            **payload,
        }
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _run_dispatcher(self, args: list[str], timeout_seconds: int) -> Dict[str, Any]:
        persistent_result = self._try_run_persistent_dispatcher(args)
        if persistent_result is not None:
            return persistent_result

        if not DISPATCHER.exists():
            raise RuntimeError(f"Dispatcher script is missing: {DISPATCHER}")

        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["MINI_ORCHESTRATOR_DISPATCHER_BEST_EFFORT_LOGS"] = "1"
        completed = subprocess.run(
            [sys.executable, str(DISPATCHER), *args],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=timeout_seconds,
            check=False,
        )
        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        try:
            payload = json.loads(stdout) if stdout else {}
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Dispatcher returned non-JSON output: {stdout[:800]}") from exc

        if completed.returncode != 0:
            message = payload.get("error") if isinstance(payload, dict) else None
            raise RuntimeError(message or stderr or f"Dispatcher failed with exit code {completed.returncode}.")

        if stderr and isinstance(payload, dict):
            payload.setdefault("stderr", stderr)
        return payload

    def _try_run_persistent_dispatcher(self, args: list[str]) -> Dict[str, Any] | None:
        if any(flag in args for flag in ("--dry-run", "--chain", "--plan-only", "--from-worknest")):
            return None
        task = ""
        if "--task-file" in args:
            index = args.index("--task-file")
            if index + 1 >= len(args):
                return None
            task_path = Path(args[index + 1])
            if not task_path.is_absolute():
                task_path = (ROOT / task_path).resolve()
            task = task_path.read_text(encoding="utf-8-sig")
        elif "--task" in args:
            index = args.index("--task")
            if index + 1 >= len(args):
                return None
            task = args[index + 1]
        if not task.strip():
            return None
        is_translation_helper = "Translate one mini-orchestrator work-package field" in task

        model = None
        if "--model" in args:
            index = args.index("--model")
            if index + 1 < len(args):
                model = args[index + 1]

        turn_timeout_seconds = 120.0
        if "--turn-timeout-seconds" in args:
            index = args.index("--turn-timeout-seconds")
            if index + 1 < len(args):
                turn_timeout_seconds = float(args[index + 1])

        return self.dispatcher_service.run_single(
            task,
            model=model,
            turn_timeout_seconds=turn_timeout_seconds,
            use_worker_models="--use-codex-default-models" not in args,
            reuse_thread=is_translation_helper,
            compact_prompt=is_translation_helper,
        )

    def _dispatcher_failure_detail(self, result: Dict[str, Any]) -> str:
        stderr = str(result.get("stderr") or "").strip()
        if stderr:
            return stderr[:800]

        log_value = str(result.get("log") or "").strip()
        if not log_value:
            return ""
        log_path = (ROOT / log_value).resolve()
        try:
            log_path.relative_to(ROOT)
        except ValueError:
            return ""
        if not log_path.exists():
            return ""

        detail = ""
        try:
            with log_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    event_type = event.get("type")
                    if event_type == "codex_notification":
                        message = event.get("message")
                        if isinstance(message, dict) and message.get("method") == "error":
                            params = message.get("params")
                            error = params.get("error") if isinstance(params, dict) else None
                            if isinstance(error, dict):
                                detail = str(error.get("message") or "").strip()
                    elif event_type in {"error", "agent_error"}:
                        detail = str(event.get("message") or event.get("error") or "").strip()
        except OSError:
            return ""
        return detail[:800]

    def _task_from_payload(self, payload: Dict[str, Any]) -> str:
        task = str(payload.get("task") or payload.get("goal") or "").strip()
        if not task:
            raise ValueError("Field 'task' is required.")
        return task

    def _agent_flow_id(self) -> str:
        prefix = "/api/agent-flows/"
        path = self._path()
        if not path.startswith(prefix):
            return ""
        return path.removeprefix(prefix).strip("/")

    def do_POST(self) -> None:
        path = self._path()
        if path not in {
            "/api/run",
            "/api/dispatcher/plan",
            "/api/dispatcher/run",
            "/api/agents/chat",
            "/api/agents/chat-warmup",
            "/api/agents/default-card",
            "/api/agents/compile",
            "/api/agents/run",
            "/api/agents/translate-work-package",
            "/api/agents/translation-log",
            "/api/agent-flows",
            "/api/daemon/run",
            "/api/daemon/review",
            "/api/symphony/refresh",
            "/api/symphony/runs",
            "/api/worknest/claim",
            "/api/worknest/complete",
        } and not (
            path.startswith("/api/agent-flows/")
            and (path.endswith("/validate") or path.endswith("/compile"))
        ):
            self._http_error(404, "Unknown endpoint.")
            return

        try:
            payload = self._read_json()
        except ValueError as exc:
            self._http_error(400, str(exc))
            return

        if path == "/api/agent-flows":
            try:
                flow = create_agent_flow(payload, ROOT)
                self._json_response(201, {"flow": flow})
            except AgentFlowError as exc:
                self._http_error(400, str(exc))
            except Exception as exc:
                self._http_error(500, str(exc))
            return

        if path == "/api/daemon/run":
            try:
                if payload.get("dryRun") is not True:
                    self._http_error(400, "Single-card daemon MVP currently requires dryRun=true.")
                    return
                manifest_id = str(payload.get("manifestId") or "").strip()
                profile_snapshot_id = str(payload.get("profileSnapshotId") or "").strip()
                if not manifest_id:
                    self._http_error(400, "Field 'manifestId' is required.")
                    return
                manifest = read_compiled_manifest(manifest_id, ROOT)
                task_value = payload.get("task")
                task = task_value if isinstance(task_value, dict) else {}
                if profile_snapshot_id:
                    state = run_single_card_dry_run(manifest, profile_snapshot_id, ROOT, task=task)
                else:
                    state = run_manifest_dry_run(
                        manifest,
                        ROOT,
                        task=task,
                        reviewer_verdict=str(payload.get("reviewerVerdict") or "done"),
                    )
                self._json_response(201, {"run": state})
            except (AgentFlowError, ValueError) as exc:
                status = 404 if "not found" in str(exc).lower() else 400
                self._http_error(status, str(exc))
            except Exception as exc:
                self._http_error(500, str(exc))
            return

        if path == "/api/daemon/review":
            try:
                run = set_run_review_decision(
                    str(payload.get("runId") or "").strip(),
                    str(payload.get("decision") or "").strip(),
                    ROOT,
                )
                self._json_response(200, {"run": run})
            except ValueError as exc:
                status = 404 if "not found" in str(exc).lower() else 400
                self._http_error(status, str(exc))
            except Exception as exc:
                self._http_error(500, str(exc))
            return

        if path == "/api/symphony/runs":
            try:
                state_payload = build_symphony_live_runs_from_url()
                orchestration_mode = str(payload.get("orchestrationMode") or "").strip()
                wait_for_completion = payload.get("waitForCompletion") is True
                if orchestration_mode == "mini-owned-chain" or wait_for_completion:
                    state_url = str(state_payload.get("stateUrl") or "").strip()
                    if not state_url:
                        self._http_error(502, "Symphony state URL is required for Mini-owned chain execution.")
                        return
                    chain_result = SymphonyGateway().run_mini_owned_chain(
                        payload,
                        state_url=state_url,
                        timeout_per_step_seconds=float(payload.get("timeoutPerStepSeconds") or 300),
                        poll_interval_seconds=float(payload.get("pollIntervalSeconds") or 5),
                    )
                    run = create_symphony_gateway_run(ROOT, payload, state_payload, submit=False)
                    now = datetime.now(timezone.utc).isoformat()
                    run["status"] = "done" if chain_result.status == "done" else chain_result.status
                    run["currentAgent"] = "Mini Orchestrator chain"
                    run["lastEvent"] = chain_result.message
                    run["lastError"] = "" if chain_result.status == "done" else chain_result.message
                    run["updatedAt"] = now
                    run["approval"] = {"required": chain_result.status not in {"done"}, "count": 0}
                    run["outputs"] = {
                        str(item.get("agentId") or item.get("agentName") or item.get("agentIndex")): item.get("summary")
                        for item in chain_result.outputs
                    }
                    for step in chain_result.steps:
                        index = int(step.get("agentIndex") or 0)
                        if index < len(run.get("stages") or []):
                            stage = run["stages"][index]
                            stage["status"] = "done" if step.get("status") in {"done", "completed"} else step.get("status")
                            stage["statusLabel"] = str(stage["status"]).replace("_", " ").title()
                            stage["lastEvent"] = step.get("message") or str(step.get("status") or "")
                            stage["completedAt"] = now if stage["status"] == "done" else None
                    run["taskCard"] = {
                        "owner": "mini-orchestrator",
                        "status": run["status"],
                        "checklist": chain_result.checklist,
                        "chainOwner": "mini-orchestrator",
                    }
                    run["symphony"]["miniOwnedChain"] = {
                        "status": chain_result.status,
                        "requestId": chain_result.request_id,
                        "steps": chain_result.steps,
                        "outputs": chain_result.outputs,
                    }
                    runtime_store.upsert_json_document(ROOT, "symphony_runs", str(run["runId"]), run)
                    self._json_response(201, run)
                    return
                self._json_response(202, create_symphony_gateway_run(ROOT, payload, state_payload, submit=True))
            except SymphonyDaemonError as exc:
                self._http_error(502, str(exc))
            except ValueError as exc:
                self._http_error(400, str(exc))
            except Exception as exc:
                self._http_error(500, str(exc))
            return

        if path == "/api/symphony/refresh":
            try:
                self._json_response(202, refresh_symphony_state())
            except SymphonyDaemonError as exc:
                self._http_error(502, str(exc))
            except Exception as exc:
                self._http_error(500, str(exc))
            return

        if path == "/api/worknest/claim":
            try:
                project = str(payload.get("project") or "mini-orchestrator").strip()
                task = WorkNestLifecycleBridge(root=ROOT).claim_next_task(project)
                self._json_response(200, {"task": task.__dict__ if task else None})
            except WorkNestBridgeError as exc:
                self._http_error(502, str(exc))
            except Exception as exc:
                self._http_error(500, str(exc))
            return

        if path == "/api/worknest/complete":
            try:
                review_decision = str(payload.get("reviewDecision") or "").strip().casefold()
                accepted = payload.get("accepted") is True or review_decision == "done"
                status_value = str(payload.get("status") or "").strip().casefold()
                if status_value == "done" and not accepted:
                    self._http_error(400, "WorkNest done completion requires reviewDecision='done' or accepted=true.")
                    return
                changed_files_value = payload.get("changedFiles")
                checks_value = payload.get("checks")
                result = WorkNestLifecycleBridge(root=ROOT).complete_task(
                    task_id=str(payload.get("taskId") or "").strip(),
                    sprint_id=str(payload.get("sprintId") or "").strip(),
                    project=str(payload.get("project") or "mini-orchestrator").strip(),
                    status=status_value,
                    summary=str(payload.get("summary") or "").strip(),
                    changed_files=[str(item) for item in changed_files_value] if isinstance(changed_files_value, list) else [],
                    checks=[str(item) for item in checks_value] if isinstance(checks_value, list) else [],
                )
                self._json_response(200, result)
            except WorkNestBridgeError as exc:
                self._http_error(400, str(exc))
            except Exception as exc:
                self._http_error(500, str(exc))
            return

        if path.startswith("/api/agent-flows/") and path.endswith("/validate"):
            flow_id = self._agent_flow_id().removesuffix("/validate").strip("/")
            if not flow_id:
                self._http_error(404, "Agent flow id is required.")
                return
            try:
                validation = validate_saved_agent_flow(
                    flow_id,
                    ROOT,
                    selected_start_agent_id=str(payload.get("selectedStartAgentId") or "").strip() or None,
                )
                self._json_response(200, validation)
            except AgentFlowError as exc:
                status = 404 if "not found" in str(exc).lower() else 400
                self._http_error(status, str(exc))
            except Exception as exc:
                self._http_error(500, str(exc))
            return

        if path.startswith("/api/agent-flows/") and path.endswith("/compile"):
            flow_id = self._agent_flow_id().removesuffix("/compile").strip("/")
            if not flow_id:
                self._http_error(404, "Agent flow id is required.")
                return
            try:
                manifest = compile_saved_agent_flow(flow_id, ROOT, payload)
                self._json_response(201, {"manifest": manifest})
            except AgentFlowError as exc:
                status = 404 if "not found" in str(exc).lower() else 400
                self._http_error(status, str(exc))
            except Exception as exc:
                self._http_error(500, str(exc))
            return

        if path == "/api/run":
            goal = str(payload.get("goal", "")).strip()
            if not goal:
                self._http_error(400, "Field 'goal' is required.")
                return

            try:
                state = self.orchestrator.run(goal)
                self._json_response(200, self.orchestrator.to_dict(state))
            except Exception as exc:
                self._http_error(500, f"Core orchestrator failed: {exc}")
            return

        if path == "/api/dispatcher/plan":
            try:
                task = self._task_from_payload(payload)
                mode = str(
                    payload.get("mode")
                    or os.environ.get("MINI_ORCHESTRATOR_PLAN_PREVIEW_MODE")
                    or "real"
                ).strip().casefold()
                if mode not in {"dry-run", "real"}:
                    self._http_error(400, "Field 'mode' must be 'dry-run' or 'real'.")
                    return
                task_args, _ = self._write_task_file(task)
                dispatcher_args = [*task_args, "--plan-only"]
                if mode == "dry-run":
                    dispatcher_args.append("--dry-run")
                result = self._run_dispatcher(
                    dispatcher_args,
                    timeout_seconds=120 if mode == "real" else 30,
                )
                result.setdefault("previewMode", mode)
                result["tech"] = build_dispatcher_tech_summary(result, ROOT)
                self._json_response(200, result)
            except ValueError as exc:
                self._http_error(400, str(exc))
            except subprocess.TimeoutExpired:
                self._http_error(504, "Dispatcher plan preview timed out.")
            except Exception as exc:
                self._json_response(502, {"error": "Dispatcher plan preview failed.", "detail": str(exc)})
            return

        if path == "/api/dispatcher/run":
            try:
                task = self._task_from_payload(payload)
                if payload.get("approved") is not True:
                    self._http_error(400, "Field 'approved' must be true before running the workflow.")
                    return
                if payload.get("background") is True:
                    run_id = "ui-" + uuid.uuid4().hex[:12]
                    task_args, _ = self._write_task_file(task, run_id)
                    chain_preset = payload.get("chainPreset")
                    dispatcher_args = [
                        *task_args,
                        *self._write_chain_preset_file(chain_preset, run_id),
                        "--run-id",
                        run_id,
                        "--chain",
                        "--turn-timeout-seconds",
                        str(APPROVED_WORKFLOW_TURN_TIMEOUT_SECONDS),
                    ]
                    if str(payload.get("mode") or "").strip().casefold() == "dry-run":
                        dispatcher_args.append("--dry-run")
                    result = self._start_dispatcher_background(dispatcher_args, run_id)
                    if isinstance(chain_preset, dict):
                        self._write_run_metadata_event(run_id, "chain_selected", chainPreset=chain_preset)
                        result["chainPreset"] = chain_preset
                    result["tech"] = build_dispatcher_tech_summary(result, ROOT)
                    self._json_response(202, result)
                    return
                run_id = "ui-" + uuid.uuid4().hex[:12]
                task_args, _ = self._write_task_file(task, run_id)
                chain_preset = payload.get("chainPreset")
                result = self._run_dispatcher(
                    [
                        *task_args,
                        *self._write_chain_preset_file(chain_preset, run_id),
                        "--run-id",
                        run_id,
                        "--chain",
                        "--turn-timeout-seconds",
                        str(APPROVED_WORKFLOW_TURN_TIMEOUT_SECONDS),
                    ],
                    timeout_seconds=APPROVED_WORKFLOW_TURN_TIMEOUT_SECONDS * 4,
                )
                if isinstance(chain_preset, dict):
                    self._write_run_metadata_event(run_id, "chain_selected", chainPreset=chain_preset)
                    result["chainPreset"] = chain_preset
                result["tech"] = build_dispatcher_tech_summary(result, ROOT)
                self._json_response(200, result)
            except ValueError as exc:
                self._http_error(400, str(exc))
            except subprocess.TimeoutExpired:
                self._http_error(504, "Approved dispatcher workflow timed out.")
            except Exception as exc:
                self._http_error(500, str(exc))
            return

        if path == "/api/agents/chat":
            try:
                response = VisualAgentApi(
                    self._run_dispatcher,
                    self._dispatcher_failure_detail,
                    visual_agent_chat=self.dispatcher_service.run_visual_agent_chat,
                ).chat(payload)
                self._json_response(200, response.payload)
            except AgentApiError as exc:
                self._http_error(exc.status, exc.message)
            except subprocess.TimeoutExpired:
                self._http_error(504, "Agent mini chat timed out.")
            except Exception as exc:
                self._http_error(500, str(exc))
            return

        if path == "/api/agents/chat-warmup":
            try:
                agent_value = payload.get("agent", {})
                if not isinstance(agent_value, dict):
                    self._http_error(400, "Field 'agent' must be an object.")
                    return
                model = str(agent_value.get("llm") or "").strip()
                if not model:
                    self._http_error(400, "Agent field 'llm' is required.")
                    return
                if model.casefold() == "rules":
                    self._json_response(200, {"status": "skipped", "reason": "rules"})
                    return
                result = self.dispatcher_service.warm_visual_agent_chat(agent_value)
                self._json_response(200, result)
            except subprocess.TimeoutExpired:
                self._http_error(504, "Agent mini chat warmup timed out.")
            except Exception as exc:
                self._http_error(500, str(exc))
            return

        if path == "/api/agents/default-card":
            try:
                card_value = payload.get("agent")
                if isinstance(card_value, dict):
                    result = persist_agent_card(card_value, ROOT)
                else:
                    result = persist_agent_card(default_project_builder_agent_card(ROOT), ROOT)
                self._json_response(200, result)
            except AgentProfileError as exc:
                self._http_error(400, str(exc))
            except Exception as exc:
                self._http_error(500, str(exc))
            return

        if path == "/api/agents/compile":
            try:
                card_value = payload.get("agent")
                card = card_value if isinstance(card_value, dict) else load_or_create_default_agent_card(ROOT)
                task = str(payload.get("task") or DEFAULT_PROJECT_BUILDER_TASK).strip()
                persist_agent_card(card, ROOT)
                profile = compile_worker_profile(card, task, ROOT)
                self._json_response(200, {"profile": profile})
            except AgentProfileError as exc:
                self._http_error(400, str(exc))
            except Exception as exc:
                self._http_error(500, str(exc))
            return

        if path == "/api/agents/run":
            try:
                if payload.get("approved") is not True:
                    self._http_error(400, "Field 'approved' must be true before running the visual agent.")
                    return
                card_value = payload.get("agent")
                card = card_value if isinstance(card_value, dict) else load_or_create_default_agent_card(ROOT)
                task = str(payload.get("task") or DEFAULT_PROJECT_BUILDER_TASK).strip()
                persist_agent_card(card, ROOT)
                profile = compile_worker_profile(card, task, ROOT)
                result = self.dispatcher_service.run_visual_agent_task(
                    profile["agent"],
                    visual_agent_task_prompt(profile),
                    str(profile["snapshotId"]),
                )
                result["profile"] = profile
                result["tech"] = build_dispatcher_tech_summary(result, ROOT)
                self._json_response(200, result)
            except AgentProfileError as exc:
                self._http_error(400, str(exc))
            except subprocess.TimeoutExpired:
                self._http_error(504, "Visual agent run timed out.")
            except Exception as exc:
                self._http_error(500, str(exc))
            return

        if path == "/api/agents/translation-log":
            event = str(payload.get("event") or "translation-log").strip()[:80]
            field = str(payload.get("field") or "").strip()[:80]
            request_id = str(payload.get("requestId") or "").strip()[:40]
            elapsed = payload.get("elapsedMs")
            detail = str(payload.get("detail") or "").strip()[:160]
            print(
                "[translation-ui-log] "
                f"event={event} field={field} requestId={request_id} "
                f"elapsedMs={elapsed} detail={detail}",
                flush=True,
            )
            self._json_response(200, {"status": "ok"})
            return

        if path == "/api/agents/translate-work-package":
            started = time.perf_counter()
            field = str(payload.get("field") or "").strip()[:80]
            text_length = len(str(payload.get("text") or ""))
            print(
                "[translation-backend] "
                f"request-start field={field} textLength={text_length}",
                flush=True,
            )
            try:
                response = VisualAgentApi(
                    self._run_dispatcher,
                    self._dispatcher_failure_detail,
                ).translate_work_package(payload)
                elapsed_ms = round((time.perf_counter() - started) * 1000)
                response.payload.setdefault("timing", {})["backendElapsedMs"] = elapsed_ms
                print(
                    "[translation-backend] "
                    f"response-send field={field} elapsedMs={elapsed_ms} "
                    f"source={response.payload.get('source')}",
                    flush=True,
                )
                self._json_response(200, response.payload)
            except AgentApiError as exc:
                elapsed_ms = round((time.perf_counter() - started) * 1000)
                print(
                    "[translation-backend] "
                    f"agent-error field={field} elapsedMs={elapsed_ms} message={exc.message}",
                    flush=True,
                )
                self._http_error(exc.status, exc.message)
            except subprocess.TimeoutExpired:
                elapsed_ms = round((time.perf_counter() - started) * 1000)
                print(
                    "[translation-backend] "
                    f"timeout field={field} elapsedMs={elapsed_ms}",
                    flush=True,
                )
                self._http_error(504, "Agent work-package translation timed out.")
            except Exception as exc:
                elapsed_ms = round((time.perf_counter() - started) * 1000)
                print(
                    "[translation-backend] "
                    f"error field={field} elapsedMs={elapsed_ms} message={exc}",
                    flush=True,
                )
                self._http_error(500, str(exc))
            return

    def do_PUT(self) -> None:
        path = self._path()
        if not path.startswith("/api/agent-flows/"):
            self._http_error(404, "Unknown endpoint.")
            return
        try:
            payload = self._read_json()
        except ValueError as exc:
            self._http_error(400, str(exc))
            return
        flow_id = self._agent_flow_id()
        if not flow_id:
            self._http_error(404, "Agent flow id is required.")
            return
        try:
            flow = update_agent_flow(flow_id, payload, ROOT)
            self._json_response(200, {"flow": flow})
        except AgentFlowError as exc:
            status = 404 if "not found" in str(exc).lower() else 400
            self._http_error(status, str(exc))
        except Exception as exc:
            self._http_error(500, str(exc))

    def do_GET(self) -> None:
        path = self._path()
        if path == "/api/agent-flows":
            try:
                self._json_response(200, {"flows": list_agent_flows(ROOT)})
            except Exception as exc:
                self._http_error(500, str(exc))
            return
        if path.startswith("/api/agent-flows/"):
            flow_id = self._agent_flow_id()
            if not flow_id:
                self._http_error(404, "Agent flow id is required.")
                return
            try:
                self._json_response(200, {"flow": read_agent_flow(flow_id, ROOT)})
            except AgentFlowError as exc:
                status = 404 if "not found" in str(exc).lower() else 400
                self._http_error(status, str(exc))
            except Exception as exc:
                self._http_error(500, str(exc))
            return
        if path == "/api/daemon/runs":
            query = self._query()
            mode = (query.get("source") or ["combined"])[0]
            self._json_response(200, build_live_runs_payload(ROOT, mode))
            return
        if path.startswith("/api/symphony/issues/"):
            issue_identifier = unquote(path.removeprefix("/api/symphony/issues/")).strip("/")
            if not issue_identifier:
                self._http_error(400, "Symphony issue identifier is required.")
                return
            try:
                self._json_response(200, fetch_symphony_issue(issue_identifier))
            except SymphonyDaemonError as exc:
                self._http_error(502, str(exc))
            except Exception as exc:
                self._http_error(500, str(exc))
            return
        if path == "/api/agents/default-card":
            try:
                card = load_or_create_default_agent_card(ROOT)
                self._json_response(200, {"card": card})
            except AgentProfileError as exc:
                self._http_error(400, str(exc))
            except Exception as exc:
                self._http_error(500, str(exc))
            return
        static_pages = {
            "/": "index.html",
            "/index.html": "index.html",
            "/agents-builder": "agents-builder.html",
            "/agents-builder.html": "agents-builder.html",
        }
        if path in static_pages:
            file_path = self.web_root / static_pages[path]
            if not file_path.exists():
                self._http_error(500, "UI file missing.")
                return
            content = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)
            return
        if path == "/health":
            self._json_response(200, {"status": "ok"})
            return
        if path == "/agent/guide":
            self._json_response(
                200,
                {
                    "service": self.service_id,
                    "name": "Mini Orchestrator",
                    "purpose": "Local web UI and API for mini-orchestrator experiments.",
                    "allowedActions": [
                        "Open the dashboard and agent builder UI.",
                        "Run dispatcher plan preview through /api/dispatcher/plan.",
                        "Run approved dispatcher workflows through /api/dispatcher/run.",
                        "Start approved dispatcher workflows in background mode and poll /api/daemon/runs for live state.",
                        "Test one visual agent card through /api/agents/chat.",
                        "Compile visual agent cards through /api/agents/compile.",
                        "Persist visual agent flows through /api/agent-flows.",
                        "Translate edited work-package helper text through the Codex dispatcher at /api/agents/translate-work-package.",
                        "Read Symphony daemon run-state records through /api/daemon/runs.",
                        "Refresh Symphony daemon observability through /api/symphony/refresh.",
                        "Read Symphony issue debug records through /api/symphony/issues/{issueIdentifier}.",
                        "Submit approved preset-based Symphony intake requests through /api/symphony/runs when the Symphony service record documents task intake.",
                        "Run Mini-owned sequential Symphony chains by posting orchestrationMode=mini-owned-chain or waitForCompletion=true to /api/symphony/runs.",
                        "Record a visible blocked Symphony gateway run when intake is not documented.",
                    ],
                    "forbiddenActions": [
                        "Do not guess or bind fallback ports when config-service has no service record.",
                        "Do not treat browser-local agent flows as executable backend workflows.",
                        "Do not store secrets in config-service records or UI payloads.",
                        "Do not treat Symphony observability refresh as task intake or task creation.",
                        "Do not claim Symphony accepted a task run unless /api/symphony/runs receives a successful response from the config-service-resolved intake endpoint.",
                    ],
                    "startup": {
                        "requiresConfigService": True,
                        "serviceId": self.service_id,
                        "portSource": "config-service service record baseUrl",
                    },
                    "contract": "/agent/contract",
                },
            )
            return
        if path == "/agent/contract":
            self._json_response(
                200,
                {
                    "service": self.service_id,
                    "version": 1,
                    "endpoints": {
                        "health": {"method": "GET", "path": "/health"},
                        "dashboard": {"method": "GET", "path": "/"},
                        "agentBuilder": {"method": "GET", "path": "/agents-builder"},
                        "coreRun": {
                            "method": "POST",
                            "path": "/api/run",
                            "required": ["goal"],
                        },
                        "dispatcherPlan": {
                            "method": "POST",
                            "path": "/api/dispatcher/plan",
                            "required": ["task"],
                        },
                        "dispatcherRun": {
                            "method": "POST",
                            "path": "/api/dispatcher/run",
                            "required": ["task", "approved"],
                            "optional": ["background", "mode"],
                        },
                        "agentMiniChat": {
                            "method": "POST",
                            "path": "/api/agents/chat",
                            "required": ["agent", "message"],
                        },
                        "defaultAgentCard": {
                            "method": "GET",
                            "path": "/api/agents/default-card",
                        },
                        "persistDefaultAgentCard": {
                            "method": "POST",
                            "path": "/api/agents/default-card",
                            "optional": ["agent"],
                        },
                        "compileAgentCard": {
                            "method": "POST",
                            "path": "/api/agents/compile",
                            "optional": ["agent", "task"],
                        },
                        "agentFlowsList": {
                            "method": "GET",
                            "path": "/api/agent-flows",
                        },
                        "agentFlowsCreate": {
                            "method": "POST",
                            "path": "/api/agent-flows",
                            "required": ["flow"],
                        },
                        "agentFlowsRead": {
                            "method": "GET",
                            "path": "/api/agent-flows/{id}",
                        },
                        "agentFlowsUpdate": {
                            "method": "PUT",
                            "path": "/api/agent-flows/{id}",
                            "required": ["flow"],
                        },
                        "agentFlowsValidate": {
                            "method": "POST",
                            "path": "/api/agent-flows/{id}/validate",
                            "optional": ["selectedStartAgentId"],
                        },
                        "agentFlowsCompile": {
                            "method": "POST",
                            "path": "/api/agent-flows/{id}/compile",
                            "required": ["approval"],
                            "optional": ["selectedStartAgentId", "maxTurnsPerNode"],
                        },
                        "daemonRun": {
                            "method": "POST",
                            "path": "/api/daemon/run",
                            "required": ["manifestId", "dryRun"],
                            "optional": ["profileSnapshotId", "reviewerVerdict"],
                            "mode": "manifest-dry-run",
                        },
                        "daemonReview": {
                            "method": "POST",
                            "path": "/api/daemon/review",
                            "required": ["runId", "decision"],
                            "decisionValues": ["done", "rework"],
                            "policy": "records local Human Review decisions; WorkNest terminal completion remains separate",
                        },
                        "symphonyRun": {
                            "method": "POST",
                            "path": "/api/symphony/runs",
                            "required": ["task", "approved"],
                            "optional": [
                                "chainPreset",
                                "mode",
                                "project",
                                "executionMode",
                                "submitToSymphony",
                                "orchestrationMode",
                                "waitForCompletion",
                                "timeoutPerStepSeconds",
                                "pollIntervalSeconds",
                            ],
                            "mode": "contract-gated-intake",
                            "policy": "requires live Symphony observability and documented task intake; default compatibility mode can submit the selected preset, while orchestrationMode=mini-owned-chain keeps Mini as task-card/checklist/chain owner and posts one next-agent handoff at a time; otherwise records a visible blocked gateway run",
                            "intakePayload": {
                                "schemaVersion": "mini-orchestrator.symphony-intake.v1",
                                "dispatchStrategies": [
                                    "one-symphony-agent-per-preset-stage",
                                    "mini-owned-single-agent-handoff",
                                ],
                                "agentTasks": "array containing either all compatibility preset stages or exactly one Mini-owned handoff agent with settings plus stage task/workPackage/codex model/reasoning/accessMode",
                            },
                        },
                        "symphonyRefresh": {
                            "method": "POST",
                            "path": "/api/symphony/refresh",
                            "optional": [],
                            "mode": "observability-control",
                            "policy": "asks Symphony to refresh its observability snapshot; does not create or mutate task runs",
                        },
                        "symphonyIssue": {
                            "method": "GET",
                            "path": "/api/symphony/issues/{issueIdentifier}",
                            "mode": "observability-read",
                            "policy": "returns Symphony issue runtime/debug details through the configured Symphony service",
                        },
                        "workNestClaim": {
                            "method": "POST",
                            "path": "/api/worknest/claim",
                            "required": ["project"],
                            "policy": "contract-gated next-task claim",
                        },
                        "workNestComplete": {
                            "method": "POST",
                            "path": "/api/worknest/complete",
                            "required": ["taskId", "sprintId", "project", "status", "summary"],
                            "optional": ["reviewDecision", "accepted", "changedFiles", "checks"],
                            "policy": "contract-gated terminal done-or-blocked only",
                        },
                        "runAgentCard": {
                            "method": "POST",
                            "path": "/api/agents/run",
                            "required": ["approved"],
                            "optional": ["agent", "task"],
                        },
                        "agentWorkPackageTranslation": {
                            "method": "POST",
                            "path": "/api/agents/translate-work-package",
                            "required": ["text", "language"],
                        },
                        "daemonRuns": {
                            "method": "GET",
                            "path": "/api/daemon/runs",
                            "optionalQuery": ["source=combined|dispatcher|symphony"],
                            "mode": "normalized-live-runs-read-only",
                        },
                    },
                    "capabilities": [
                        "orchestrator-dashboard",
                        "dispatcher-plan-preview",
                        "approved-dispatcher-workflow",
                        "agent-card-mini-chat",
                        "agent-card-compile",
                        "agent-flow-persistence",
                        "agent-flow-validation",
                        "agent-flow-compile",
                        "daemon-dry-run",
                        "worknest-lifecycle-bridge",
                        "agent-work-package-translation",
                        "symphony-daemon-dashboard",
                        "symphony-run-gateway",
                    ],
                },
            )
            return
        self._http_error(404, "Not found.")

    def log_message(self, format: str, *args) -> None:
        # keep CLI output clean for app usage
        return


def run_ui_server(orchestrator: Orchestrator, ui_config: UiConfig) -> int:
    web_root = Path(__file__).parent / "web"

    handler = _OrchestratorUIHandler
    handler.orchestrator = orchestrator
    handler.dispatcher_service = PersistentCodexDispatcher(ROOT)
    handler.web_root = web_root
    handler.service_id = ui_config.service_id
    address = (ui_config.host, ui_config.port)
    httpd = _ThreadedHttpServer(address, handler)
    url = f"http://{ui_config.host}:{ui_config.port}/"
    if ui_config.open_browser:
        webbrowser.open(url)

    print(f"Mini Orchestrator UI: {url}")
    if ui_config.base_url:
        print(f"Config-service record: {ui_config.service_id} -> {ui_config.base_url}")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down UI.")
    finally:
        handler.dispatcher_service.close()
        httpd.shutdown()
        httpd.server_close()
    return 0
