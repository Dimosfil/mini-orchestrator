from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlparse
from urllib.request import Request, urlopen
import json
import os
import uuid

from . import service_discovery
from . import runtime_store


DEFAULT_STATE_URL = "http://127.0.0.1:4000/api/v1/state"
STATE_URL_ENV = "MINI_ORCHESTRATOR_DAEMON_STATE_URL"
SERVICE_ID_ENV = "MINI_ORCHESTRATOR_SYMPHONY_SERVICE_ID"
DEFAULT_SERVICE_ID = "symphony"
LOCAL_SYMPHONY_RUN_DIR = ".mini_orchestrator/symphony-runs"
INTAKE_ENDPOINT_KEYS = ("taskIntake", "task-intake", "agentIntake", "agent-intake", "intake")


class SymphonyDaemonError(RuntimeError):
    pass


def _absolute_endpoint(base_url: str, endpoint: str) -> str:
    endpoint = endpoint.strip()
    parsed = urlparse(endpoint)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return endpoint.rstrip("/")
    return urljoin(f"{base_url.rstrip('/')}/", endpoint.lstrip("/")).rstrip("/")


def _configured_service_id() -> str:
    return os.environ.get(SERVICE_ID_ENV, DEFAULT_SERVICE_ID).strip() or DEFAULT_SERVICE_ID


def configured_api_url() -> str:
    runtime = service_discovery.resolve_service_runtime(_configured_service_id())
    api_endpoint = runtime.endpoints.get("api") or "/api/v1"
    return _absolute_endpoint(runtime.base_url, api_endpoint)


def configured_state_url() -> str:
    explicit = os.environ.get(STATE_URL_ENV)
    if explicit:
        return explicit.strip()

    runtime = service_discovery.resolve_service_runtime(_configured_service_id())
    state_endpoint = (
        runtime.endpoints.get("availability")
        or runtime.endpoints.get("state")
        or runtime.endpoints.get("contract")
        or "/api/v1/state"
    )
    return _absolute_endpoint(runtime.base_url, state_endpoint)


def configured_refresh_url() -> str:
    return f"{configured_api_url()}/refresh"


def configured_issue_url(issue_identifier: str) -> str:
    identifier = issue_identifier.strip()
    if not identifier:
        raise SymphonyDaemonError("Symphony issue identifier is required.")
    return f"{configured_api_url()}/{quote(identifier, safe='')}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _request_json(
    url: str,
    method: str = "GET",
    timeout: float = 2.0,
    payload: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    request = Request(url, method=method, headers=headers, data=data)
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


def _service_runtime() -> service_discovery.ResolvedServiceRuntime:
    try:
        return service_discovery.resolve_service_runtime(_configured_service_id())
    except service_discovery.ConfigServiceBlocker as exc:
        raise SymphonyDaemonError(f"Symphony service discovery failed: {exc}") from exc


def _configured_contract_url(runtime: service_discovery.ResolvedServiceRuntime) -> str:
    endpoint = runtime.endpoints.get("contract")
    if not endpoint:
        raise SymphonyDaemonError("Symphony service record has no endpoints.contract documenting task intake.")
    return _absolute_endpoint(runtime.base_url, endpoint)


def _configured_intake_url(runtime: service_discovery.ResolvedServiceRuntime, contract: Dict[str, Any]) -> str:
    for key in INTAKE_ENDPOINT_KEYS:
        endpoint = runtime.endpoints.get(key)
        if endpoint:
            return _absolute_endpoint(runtime.base_url, endpoint)

    contract_endpoints = contract.get("endpoints") if isinstance(contract.get("endpoints"), dict) else {}
    for key in INTAKE_ENDPOINT_KEYS:
        value = contract_endpoints.get(key)
        if isinstance(value, str) and value.strip():
            return _absolute_endpoint(runtime.base_url, value)
        if isinstance(value, dict):
            path = value.get("path")
            if isinstance(path, str) and path.strip():
                return _absolute_endpoint(runtime.base_url, path)

    raise SymphonyDaemonError(
        "Symphony contract/service record has no task-intake endpoint "
        f"({', '.join(INTAKE_ENDPOINT_KEYS)})."
    )


def fetch_symphony_state(url: str, timeout: float = 2.0) -> Dict[str, Any]:
    return _request_json(url, timeout=timeout)


def refresh_symphony_state(url: str | None = None, timeout: float = 5.0) -> Dict[str, Any]:
    try:
        refresh_url = (url or configured_refresh_url()).strip()
    except service_discovery.ConfigServiceBlocker as exc:
        raise SymphonyDaemonError(f"Symphony service discovery failed: {exc}") from exc
    return _request_json(refresh_url, method="POST", timeout=timeout)


def fetch_symphony_issue(issue_identifier: str, url: str | None = None, timeout: float = 5.0) -> Dict[str, Any]:
    try:
        issue_url = (url or configured_issue_url(issue_identifier)).strip()
    except service_discovery.ConfigServiceBlocker as exc:
        raise SymphonyDaemonError(f"Symphony service discovery failed: {exc}") from exc
    return _request_json(issue_url, timeout=timeout)


def _text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    return str(value)


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _chain_stage_names(chain_preset: Dict[str, Any]) -> list[str]:
    flow = chain_preset.get("flow") if isinstance(chain_preset.get("flow"), dict) else {}
    agents = flow.get("agents") if isinstance(flow.get("agents"), list) else []
    names = [
        _text(agent.get("name") or agent.get("role") or agent.get("preset")).strip()
        for agent in agents
        if isinstance(agent, dict)
    ]
    if names:
        return [name for name in names if name]
    stages = chain_preset.get("stages") if isinstance(chain_preset.get("stages"), list) else []
    return [_text(stage).strip() for stage in stages if _text(stage).strip()]


def _flow_agents(chain_preset: Dict[str, Any]) -> list[Dict[str, Any]]:
    flow = chain_preset.get("flow") if isinstance(chain_preset.get("flow"), dict) else {}
    agents = flow.get("agents") if isinstance(flow.get("agents"), list) else []
    normalized = [agent for agent in agents if isinstance(agent, dict)]
    if normalized:
        return normalized
    stages = chain_preset.get("stages") if isinstance(chain_preset.get("stages"), list) else []
    return [
        {"id": f"stage-{index + 1}", "name": _text(stage), "role": _text(stage), "preset": _text(stage)}
        for index, stage in enumerate(stages)
        if _text(stage).strip()
    ]


def _agent_task_from_preset_agent(index: int, agent: Dict[str, Any], global_task: Dict[str, Any]) -> Dict[str, Any]:
    work_package = agent.get("workPackage") if isinstance(agent.get("workPackage"), dict) else {}
    translations = (
        agent.get("workPackageTranslations")
        if isinstance(agent.get("workPackageTranslations"), dict)
        else {}
    )
    agent_id = _text(agent.get("id") or agent.get("name") or agent.get("role") or f"agent-{index + 1}")
    role = _text(agent.get("role") or agent.get("preset") or agent.get("name") or "agent")
    name = _text(agent.get("name") or role or agent_id)
    return {
        "index": index,
        "stageId": agent_id,
        "agent": {
            "id": agent_id,
            "name": name,
            "role": role,
            "preset": _text(agent.get("preset")),
            "label": _text(agent.get("label") or name),
        },
        "codex": {
            "model": _text(agent.get("llm") or agent.get("model")),
            "speed": _text(agent.get("speed")),
            "reasoning": _text(agent.get("reasoning")),
            "accessMode": _text(agent.get("accessMode")),
        },
        "workPackage": work_package,
        "workPackageTranslations": translations,
        "task": {
            "global": global_task,
            "currentObjective": _text(work_package.get("currentObjective") or global_task.get("title")),
            "instructions": _text(work_package.get("instructions")),
            "constraints": _text(work_package.get("constraints")),
            "expectedOutput": _text(work_package.get("expectedOutput")),
            "inputsArtifacts": _text(work_package.get("inputsArtifacts")),
            "previousOutputs": _text(work_package.get("previousOutputs")),
        },
    }


def build_symphony_intake_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if payload.get("approved") is not True:
        raise ValueError("Field 'approved' must be true before creating a Symphony run.")
    task_value = payload.get("task")
    if isinstance(task_value, dict):
        task_title = str(task_value.get("title") or task_value.get("summary") or task_value.get("task") or "").strip()
        task_id = str(task_value.get("taskId") or "").strip()
        sprint_id = str(task_value.get("sprintId") or "").strip()
        raw_task = str(task_value.get("raw") or task_title).strip()
    else:
        task_title = str(task_value or payload.get("goal") or "").strip()
        task_id = str(payload.get("taskId") or "").strip()
        sprint_id = str(payload.get("sprintId") or "").strip()
        raw_task = task_title
    if not task_title:
        raise ValueError("Field 'task' is required.")

    chain_preset = payload.get("chainPreset") if isinstance(payload.get("chainPreset"), dict) else {}
    agents = _flow_agents(chain_preset)
    if not agents:
        agents = [
            {"id": "default-planner", "name": "Planner", "role": "planner", "preset": "planner"},
            {"id": "default-executor", "name": "Executor", "role": "executor", "preset": "executor"},
            {"id": "default-reviewer", "name": "Reviewer", "role": "reviewer", "preset": "reviewer"},
        ]
    global_task = {
        "taskId": task_id,
        "sprintId": sprint_id,
        "project": str(payload.get("project") or "mini-orchestrator").strip(),
        "title": task_title,
        "raw": raw_task,
    }
    return {
        "schemaVersion": "mini-orchestrator.symphony-intake.v1",
        "approved": True,
        "requestedAt": _utc_now(),
        "requestedBy": "mini-orchestrator",
        "executionMode": "symphony",
        "dispatchStrategy": "one-symphony-agent-per-preset-stage",
        "task": global_task,
        "chainPreset": {
            "id": _text(chain_preset.get("id") or chain_preset.get("chainPresetId")),
            "name": _text(
                chain_preset.get("name")
                or (
                    chain_preset.get("flow", {}).get("name")
                    if isinstance(chain_preset.get("flow"), dict)
                    else ""
                )
            ),
            "raw": chain_preset,
        },
        "agentTasks": [_agent_task_from_preset_agent(index, agent, global_task) for index, agent in enumerate(agents)],
        "handoffPolicy": {
            "taskCardIsSingleUserVisibleUnit": True,
            "eachPresetAgentReceivesOwnSettingsAndStageTask": True,
            "previousStageOutputsBecomeNextStageContext": True,
        },
    }


def submit_symphony_intake(payload: Dict[str, Any], timeout: float = 10.0) -> Dict[str, Any]:
    runtime = _service_runtime()
    contract_url = _configured_contract_url(runtime)
    contract = _request_json(contract_url, timeout=5.0)
    intake_url = _configured_intake_url(runtime, contract)
    intake_payload = build_symphony_intake_payload(payload)
    response = _request_json(intake_url, method="POST", timeout=timeout, payload=intake_payload)
    return {
        "serviceId": runtime.service_id,
        "contractUrl": contract_url,
        "intakeUrl": intake_url,
        "contract": contract,
        "request": intake_payload,
        "response": response,
    }


def _summary_for_runs(runs: list[Dict[str, Any]]) -> Dict[str, int]:
    return {
        "total": len(runs),
        "active": sum(1 for run in runs if run.get("status") in {"running", "retrying", "queued", "waiting_approval"}),
        "blocked": sum(1 for run in runs if run.get("status") == "blocked"),
        "done": sum(1 for run in runs if run.get("status") == "done"),
        "failed": sum(1 for run in runs if run.get("status") == "failed"),
    }


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


def build_symphony_daemon_summary_run(state: Dict[str, Any], state_url: str, generated_at: str) -> Dict[str, Any]:
    counts = state.get("counts") if isinstance(state.get("counts"), dict) else {}
    codex_totals = state.get("codex_totals") if isinstance(state.get("codex_totals"), dict) else {}
    running = _int(counts.get("running") if counts else len(state.get("running") or []))
    retrying = _int(counts.get("retrying") if counts else len(state.get("retrying") or []))
    blocked = _int(counts.get("blocked") if counts else len(state.get("blocked") or []))
    total = running + retrying + blocked
    status = "running" if running else "retrying" if retrying else "blocked" if blocked else "idle"
    last_event = (
        f"running={running}, retrying={retrying}, blocked={blocked}, "
        f"tokens={_int(codex_totals.get('total_tokens') or codex_totals.get('total'))}"
    )
    return {
        "schemaVersion": 1,
        "runId": "symphony-daemon-summary",
        "sourceKey": "symphony",
        "sourceLabel": "Symphony",
        "status": status,
        "mode": "symphony-daemon-summary",
        "currentAgent": "Symphony daemon",
        "task": {
            "taskId": "symphony-daemon",
            "title": "Symphony daemon snapshot",
            "summary": last_event,
            "raw": state_url,
        },
        "profileSnapshotId": "symphony-daemon",
        "thread": {"threadId": None, "currentTurnId": None, "turnCount": 0, "workers": []},
        "tokens": {
            "input": _int(codex_totals.get("input_tokens") or codex_totals.get("input")),
            "output": _int(codex_totals.get("output_tokens") or codex_totals.get("output")),
            "total": _int(codex_totals.get("total_tokens") or codex_totals.get("total")),
        },
        "artifacts": {
            "eventLogPath": state_url,
            "workspaceGenerated": False,
            "durableProjectMemory": False,
            "privateRuntimeData": True,
        },
        "lastEvent": last_event,
        "lastError": "",
        "approval": {"required": False, "count": 0},
        "chainPreset": {},
        "stages": [
            {
                "agent": "symphony-daemon",
                "label": "Symphony daemon",
                "status": status,
                "statusLabel": status.replace("_", " ").title(),
                "startedAt": generated_at,
                "completedAt": None,
                "threadId": None,
                "turnCount": 0,
                "model": None,
                "tokens": _int(codex_totals.get("total_tokens") or codex_totals.get("total")),
                "lastEvent": last_event,
                "output": json.dumps(
                    {
                        "counts": {"running": running, "retrying": retrying, "blocked": blocked, "total": total},
                        "codex_totals": codex_totals,
                        "rate_limits": state.get("rate_limits"),
                    },
                    ensure_ascii=False,
                ),
            }
        ],
        "eventTypes": {},
        "createdAt": generated_at,
        "updatedAt": generated_at,
        "reviewerVerdict": None,
        "stale": {"isStale": False, "reason": "", "lastEventAt": generated_at, "thresholdSeconds": 0},
        "outputs": {},
        "daemonSnapshot": {
            "counts": {"running": running, "retrying": retrying, "blocked": blocked, "total": total},
            "codexTotals": codex_totals,
            "rateLimits": state.get("rate_limits"),
            "stateUrl": state_url,
        },
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

    runs.append(build_symphony_daemon_summary_run(state, state_url, generated_at))

    summary = _summary_for_runs([run for run in runs if run.get("mode") != "symphony-daemon-summary"])
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
    try:
        state_url = (url or configured_state_url()).strip()
    except service_discovery.ConfigServiceBlocker as exc:
        raise SymphonyDaemonError(f"Symphony service discovery failed: {exc}") from exc
    state = fetch_symphony_state(state_url, timeout=timeout)
    return build_symphony_live_runs(state, state_url)


def _local_symphony_run_dir(root: Path) -> Path:
    return root / LOCAL_SYMPHONY_RUN_DIR


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def create_symphony_gateway_run(
    root: Path,
    payload: Dict[str, Any],
    state_payload: Dict[str, Any] | None = None,
    *,
    submit: bool = False,
) -> Dict[str, Any]:
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

    now = _utc_now()
    chain_preset = payload.get("chainPreset") if isinstance(payload.get("chainPreset"), dict) else {}
    intake_payload = build_symphony_intake_payload(payload)
    agent_tasks = intake_payload.get("agentTasks") if isinstance(intake_payload.get("agentTasks"), list) else []
    stage_names = [
        _text(task.get("agent", {}).get("name") if isinstance(task.get("agent"), dict) else "").strip()
        for task in agent_tasks
        if isinstance(task, dict)
    ] or _chain_stage_names(chain_preset) or ["planner", "executor", "reviewer"]
    submission: Dict[str, Any] | None = None
    submission_error = ""
    if submit:
        try:
            submission = submit_symphony_intake(payload)
        except SymphonyDaemonError as exc:
            submission_error = str(exc)
        except Exception as exc:
            submission_error = f"Symphony intake submission failed: {exc}"
    submitted = isinstance(submission, dict)
    accepted_status = "queued"
    if submitted:
        response = submission.get("response")
        if isinstance(response, dict):
            accepted_status = _text(response.get("status") or response.get("state") or "queued", "queued")
    state_error = ""
    state_available = state_payload is not None
    state_url = ""
    if isinstance(state_payload, dict):
        state_url = _text(state_payload.get("stateUrl"))
    run_id = f"symphony-gateway-{uuid.uuid4().hex[:12]}"
    run = {
        "schemaVersion": 1,
        "runId": run_id,
        "sourceKey": "symphony",
        "sourceLabel": "Symphony",
        "status": accepted_status if submitted else "blocked",
        "mode": "symphony-gateway",
        "currentAgent": "Symphony intake",
        "task": {
            "taskId": task_id or run_id,
            "sprintId": sprint_id,
            "project": str(payload.get("project") or "mini-orchestrator").strip(),
            "title": task_title,
            "raw": task_title,
        },
        "profileSnapshotId": "symphony-gateway",
        "thread": {"threadId": None, "currentTurnId": None, "turnCount": 0, "workers": []},
        "tokens": {"input": 0, "output": 0, "total": 0},
        "lastEvent": (
            "Submitted preset-based task payload to Symphony intake."
            if submitted
            else "Symphony observability is live; external task intake is not exposed by Symphony yet."
        ),
        "lastError": "" if submitted else (submission_error or "symphony-intake-missing"),
        "artifacts": {
            "eventLogPath": str((Path(LOCAL_SYMPHONY_RUN_DIR) / f"{run_id}.json").as_posix()),
            "workspaceGenerated": False,
            "durableProjectMemory": False,
            "privateRuntimeData": True,
        },
        "approval": {"required": not submitted, "count": 0 if submitted else 1},
        "chainPreset": chain_preset,
        "stages": [
            {
                "agent": stage,
                "label": stage,
                "status": "queued" if submitted else ("waiting_approval" if index == 0 else "pending"),
                "statusLabel": "Queued" if submitted else ("Waiting Intake" if index == 0 else "Pending"),
                "startedAt": now if index == 0 else None,
                "completedAt": None,
                "threadId": None,
                "turnCount": 0,
                "model": (
                    _text(agent_tasks[index].get("codex", {}).get("model"))
                    if index < len(agent_tasks) and isinstance(agent_tasks[index], dict) and isinstance(agent_tasks[index].get("codex"), dict)
                    else None
                ),
                "tokens": 0,
                "lastEvent": (
                    "Submitted to Symphony intake."
                    if submitted
                    else ("Waiting for Symphony task-intake endpoint." if index == 0 else "")
                ),
                "output": "",
            }
            for index, stage in enumerate(stage_names)
        ],
        "eventTypes": {
            "symphony_gateway_request": 1,
            "symphony_intake_submitted" if submitted else "symphony_intake_blocked": 1,
        },
        "createdAt": now,
        "updatedAt": now,
        "reviewerVerdict": None,
        "stale": {"isStale": False, "reason": "", "lastEventAt": now, "thresholdSeconds": 0},
        "outputs": {},
        "requiredContract": {
            "serviceId": "symphony",
            "expectedCapability": "task-intake",
            "expectedEndpoint": "endpoints.taskIntake | endpoints.agentIntake | endpoints.intake",
            "expectedContract": "endpoints.contract documents the task-intake payload schema",
            "observedEndpoints": ["GET /api/v1/state", "POST /api/v1/refresh", "GET /api/v1/{issue_identifier}"],
        },
        "symphony": {
            "stateAvailable": state_available,
            "stateUrl": state_url,
            "stateSummary": state_payload.get("summary") if isinstance(state_payload, dict) else {},
            "stateError": state_error,
            "intakeSubmitted": submitted,
            "submissionError": submission_error,
            "submission": submission,
            "intakePayload": intake_payload,
        },
    }
    runtime_store.upsert_json_document(root, "symphony_runs", run_id, run)
    return run


def build_local_symphony_gateway_runs(root: Path) -> Dict[str, Any]:
    runs: list[Dict[str, Any]] = runtime_store.list_json_documents(root, "symphony_runs")
    seen = {str(run.get("runId") or "") for run in runs}
    run_dir = _local_symphony_run_dir(root)
    if run_dir.exists():
        for path in sorted(run_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict) and str(payload.get("runId") or "") not in seen:
                runs.append(payload)
    return {
        "source": "symphony-gateway",
        "sourceLabel": "Symphony",
        "generatedAt": _utc_now(),
        "summary": _summary_for_runs(runs),
        "profiles": {
            "symphony-gateway": {
                "displayName": "Symphony Intake Gateway",
                "role": "gateway",
                "model": "-",
            }
        },
        "runs": runs,
    }
