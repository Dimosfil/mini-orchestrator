from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlparse
from urllib.request import Request, urlopen
import json
import os
import re
import shutil
import uuid

from . import service_discovery
from .agent_flows import AgentFlowError, execution_order_for_flow
from . import runtime_store
from .model_defaults import coordinator_model, executor_model, reviewer_model


DEFAULT_STATE_URL = "http://127.0.0.1:4000/api/v1/state"
STATE_URL_ENV = "MINI_ORCHESTRATOR_DAEMON_STATE_URL"
SERVICE_ID_ENV = "MINI_ORCHESTRATOR_SYMPHONY_SERVICE_ID"
DEFAULT_SERVICE_ID = "symphony"
LOCAL_SYMPHONY_RUN_DIR = ".mini_orchestrator/symphony-runs"
ARTIFACT_STORAGE_ROOT = ".mini_orchestrator/test-runs"
ARTIFACT_CONTRACT_MARKER = ".artifact-contract.json"
ARTIFACT_CONTRACT_SCHEMA_VERSION = "mini-orchestrator.artifact-contract.v1"
WORKSPACE_ARTIFACT_HINTS = {
    "artifactManifest.json",
    "backend",
    "frontend",
    "index.html",
    "main.py",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "src",
}
WORKSPACE_COPY_EXCLUDE_NAMES = {
    ".env",
    ".git",
    ".next",
    ".nuxt",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "codex-workpad.md",
    "dist",
    "node_modules",
}
INTAKE_ENDPOINT_KEYS = ("taskIntake", "task-intake", "agentIntake", "agent-intake", "intake")
MINI_ORIGIN_EXTERNAL_TOOL_POLICY = (
    "Mini Orchestrator owns this run locally. Do not use Linear, external task managers, "
    "MCP authorization flows, OAuth browser approval, or SaaS tracker tools unless the "
    "user explicitly requested that integration for this task. If such access appears "
    "necessary, stop and report a blocker instead of opening an authorization request."
)
CYRILLIC_TRANSLITERATION = str.maketrans(
    {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "e",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "sch",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
    }
)


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


def _append_policy_text(value: Any, policy: str) -> str:
    text = _text(value).strip()
    if policy in text:
        return text
    return f"{text}\n\n{policy}" if text else policy


def _artifact_contract(payload: Dict[str, Any]) -> Dict[str, Any]:
    return payload.get("artifactContract") if isinstance(payload.get("artifactContract"), dict) else {}


def _artifact_contract_policy(contract: Dict[str, Any]) -> str:
    relative_path = _text(contract.get("relativePath") or contract.get("path")).strip()
    absolute_path = _text(contract.get("absolutePath")).strip()
    path_hint = relative_path or absolute_path or ARTIFACT_STORAGE_ROOT
    return (
        "Artifact storage contract: generated software/application output for this run must be written "
        f"only under {path_hint}. Use the selected project slug and version folder, do not overwrite older "
        "versions, and do not treat a Symphony workspace or launch-desk as the final artifact unless the "
        "user explicitly named that folder. Return the artifact path, entry point, run commands, verification "
        "performed, and remaining gaps. If the artifact cannot be created at that path, report a blocker."
    )


def _artifact_expected_output_policy(contract: Dict[str, Any]) -> str:
    relative_path = _text(contract.get("relativePath") or contract.get("path")).strip()
    path_hint = relative_path or ARTIFACT_STORAGE_ROOT
    return (
        f"Artifact report required: artifactPath={path_hint}; include entry point, run/build/test commands, "
        "verification evidence, and known gaps."
    )


def ensure_artifact_contract(payload: Dict[str, Any], root: Path, *, reserve: bool = False) -> Dict[str, Any]:
    """Return a payload with a concrete versioned artifact target inside the project root."""
    existing = _artifact_contract(payload)
    task_title, task_id, _sprint_id, raw_task = _task_parts(payload)
    slug = _artifact_slug(
        _text(existing.get("slug") or payload.get("artifactSlug")).strip()
        or _derive_artifact_slug(raw_task or task_title)
    )
    version = _artifact_version(
        _text(existing.get("version") or payload.get("artifactVersion")).strip()
        or _next_artifact_version(root, slug)
    )
    relative_path = _artifact_relative_path(slug, version)
    absolute_path = root / Path(relative_path)
    contract = {
        "schemaVersion": ARTIFACT_CONTRACT_SCHEMA_VERSION,
        "required": True,
        "storageRoot": ARTIFACT_STORAGE_ROOT,
        "slug": slug,
        "version": version,
        "relativePath": relative_path,
        "absolutePath": str(absolute_path),
        "manifestPath": str(absolute_path / "artifactManifest.json"),
        "readmePath": str(absolute_path / "README.md"),
        "markerPath": str(absolute_path / ARTIFACT_CONTRACT_MARKER),
        "taskId": task_id,
        "taskTitle": task_title,
    }
    enriched = dict(payload)
    enriched["artifactContract"] = {**existing, **contract}
    if reserve:
        _reserve_artifact_contract(root, enriched["artifactContract"])
    return enriched


def inspect_artifact_contract(root: Path, contract: Dict[str, Any]) -> Dict[str, Any]:
    relative_path = _text(contract.get("relativePath") or contract.get("path")).strip()
    if not relative_path:
        return {
            "status": "missing",
            "message": "Artifact contract did not include a relative path.",
            "contentFileCount": 0,
        }
    artifact_path = root / Path(relative_path)
    try:
        artifact_path.resolve().relative_to(root.resolve())
    except ValueError:
        return {
            "status": "invalid",
            "path": str(artifact_path),
            "relativePath": relative_path,
            "message": "Artifact path escapes the project root.",
            "contentFileCount": 0,
        }
    if not artifact_path.exists():
        return {
            "status": "missing",
            "path": str(artifact_path),
            "relativePath": relative_path,
            "message": "Artifact version folder was not created.",
            "contentFileCount": 0,
        }
    content_files = [
        path
        for path in artifact_path.rglob("*")
        if path.is_file() and path.name != ARTIFACT_CONTRACT_MARKER
    ]
    if not content_files:
        return {
            "status": "empty",
            "path": str(artifact_path),
            "relativePath": relative_path,
            "message": "Artifact version folder exists but contains no generated application files.",
            "contentFileCount": 0,
        }
    return {
        "status": "found",
        "path": str(artifact_path),
        "relativePath": relative_path,
        "message": "Artifact version folder contains generated files.",
        "contentFileCount": len(content_files),
        "sampleFiles": [str(path.relative_to(artifact_path).as_posix()) for path in content_files[:12]],
    }


def materialize_artifact_from_issues(
    root: Path,
    contract: Dict[str, Any],
    chain_outputs: list[Dict[str, Any]],
) -> Dict[str, Any]:
    """Copy generated workspace content into the versioned project artifact folder when possible."""
    target_status = inspect_artifact_contract(root, contract)
    if target_status.get("status") == "found":
        return {"status": "skipped", "message": "Artifact folder already contains generated files."}

    relative_path = _text(contract.get("relativePath")).strip()
    if not relative_path:
        return {"status": "missing_contract", "message": "Artifact contract does not include a relative path."}
    target = root / Path(relative_path)
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError:
        return {"status": "invalid_contract", "message": "Artifact target escapes the project root."}

    workspaces = _workspace_paths_from_chain_outputs(chain_outputs)
    for workspace_path in workspaces:
        source_root = Path(workspace_path)
        source = _workspace_artifact_source(source_root, contract)
        if source is None:
            continue
        try:
            if source.resolve() == target.resolve():
                continue
        except OSError:
            continue
        copied = _copy_workspace_artifact(source, target)
        if copied:
            return {
                "status": "materialized",
                "sourcePath": str(source),
                "targetPath": str(target),
                "copiedCount": len(copied),
                "copiedSample": copied[:12],
            }
    return {
        "status": "not_found",
        "message": "No generated application content was found in Symphony workspaces.",
        "workspaceCount": len(workspaces),
    }


def _workspace_paths_from_chain_outputs(chain_outputs: list[Dict[str, Any]]) -> list[str]:
    paths: list[str] = []
    preferred: list[str] = []
    for output in chain_outputs:
        if not isinstance(output, dict):
            continue
        issues = output.get("issues") if isinstance(output.get("issues"), list) else []
        agent_text = _text(output.get("agentId") or output.get("agentName")).casefold()
        for issue in issues:
            if not isinstance(issue, dict):
                continue
            path = _text(
                issue.get("workspace_path")
                or issue.get("workspacePath")
                or issue.get("workspace")
                or issue.get("workspace_dir")
            ).strip()
            if not path or path in paths or path in preferred:
                continue
            issue_text = _text(
                issue.get("issue_id")
                or issue.get("issue_identifier")
                or issue.get("identifier")
            ).casefold()
            if "executor" in agent_text or "executor" in issue_text:
                preferred.append(path)
            else:
                paths.append(path)
    return [*preferred, *paths]


def _workspace_artifact_source(workspace_path: Path, contract: Dict[str, Any]) -> Path | None:
    if not workspace_path.exists() or not workspace_path.is_dir():
        return None
    relative_path = _text(contract.get("relativePath")).strip()
    if relative_path:
        nested_contract_target = workspace_path / Path(relative_path)
        if nested_contract_target.exists() and nested_contract_target.is_dir() and _has_artifact_hints(nested_contract_target):
            return nested_contract_target
    if _has_artifact_hints(workspace_path):
        return workspace_path
    for child in workspace_path.iterdir():
        if child.is_dir() and child.name not in WORKSPACE_COPY_EXCLUDE_NAMES and _has_artifact_hints(child):
            return child
    return None


def _has_artifact_hints(path: Path) -> bool:
    try:
        names = {child.name for child in path.iterdir()}
    except OSError:
        return False
    return bool(names & WORKSPACE_ARTIFACT_HINTS)


def _copy_workspace_artifact(source: Path, target: Path) -> list[str]:
    target.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for child in source.iterdir():
        if child.name in WORKSPACE_COPY_EXCLUDE_NAMES:
            continue
        destination = target / child.name
        if child.is_dir():
            shutil.copytree(
                child,
                destination,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(*WORKSPACE_COPY_EXCLUDE_NAMES),
            )
            copied.append(child.name)
        elif child.is_file():
            shutil.copy2(child, destination)
            copied.append(child.name)
    return copied


def _reserve_artifact_contract(root: Path, contract: Dict[str, Any]) -> None:
    relative_path = _text(contract.get("relativePath")).strip()
    if not relative_path:
        return
    artifact_path = root / Path(relative_path)
    try:
        artifact_path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise SymphonyDaemonError("Artifact contract path must stay inside the project root.") from exc
    artifact_path.mkdir(parents=True, exist_ok=True)
    marker = artifact_path / ARTIFACT_CONTRACT_MARKER
    marker.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _artifact_relative_path(slug: str, version: str) -> str:
    return (Path(ARTIFACT_STORAGE_ROOT) / slug / version).as_posix()


def _next_artifact_version(root: Path, slug: str) -> str:
    slug_dir = root / Path(ARTIFACT_STORAGE_ROOT) / slug
    highest = 0
    if slug_dir.exists():
        for child in slug_dir.iterdir():
            match = re.fullmatch(r"v(\d{3,})", child.name)
            if child.is_dir() and match:
                highest = max(highest, int(match.group(1)))
    return f"v{highest + 1:03d}"


def _artifact_version(value: str) -> str:
    text = value.strip().lower()
    if re.fullmatch(r"v\d{3,}", text):
        return text
    digits = re.sub(r"\D", "", text)
    if digits:
        return f"v{int(digits):03d}"
    return "v001"


def _artifact_slug(value: str) -> str:
    text = value.strip().lower()
    text = text.translate(CYRILLIC_TRANSLITERATION)
    text = text.replace("срм", "crm")
    slug = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:80].strip("-") or "generated-app"


def _derive_artifact_slug(task_text: str) -> str:
    lower = task_text.casefold()
    has_crm = "crm" in lower or "срм" in lower
    if "стомат" in lower or "dental" in lower or "dentist" in lower:
        return "dental-crm" if has_crm else "dental-app"
    if "аптек" in lower or "pharmacy" in lower:
        return "pharmacy-crm" if has_crm else "pharmacy-app"
    if has_crm:
        return "crm-app"
    return _artifact_slug(task_text)[:80] or "generated-app"


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
        agent_by_id = {_text(agent.get("id")).strip(): agent for agent in normalized}
        try:
            flow_for_validation = {**flow, "updatedAt": _text(chain_preset.get("updatedAt") or flow.get("updatedAt") or _utc_now())}
            ordered_ids = execution_order_for_flow(flow_for_validation)
        except AgentFlowError as exc:
            raise SymphonyDaemonError(f"Selected chain preset is not executable: {exc}") from exc
        ordered = [agent_by_id[agent_id] for agent_id in ordered_ids if agent_id in agent_by_id]
        return ordered or normalized
    stages = chain_preset.get("stages") if isinstance(chain_preset.get("stages"), list) else []
    return [
        {"id": f"stage-{index + 1}", "name": _text(stage), "role": _text(stage), "preset": _text(stage)}
        for index, stage in enumerate(stages)
        if _text(stage).strip()
    ]


def _agent_task_from_preset_agent(
    index: int,
    agent: Dict[str, Any],
    global_task: Dict[str, Any],
    *,
    checklist_item: Dict[str, Any] | None = None,
    previous_outputs: list[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    source_work_package = agent.get("workPackage") if isinstance(agent.get("workPackage"), dict) else {}
    work_package = dict(source_work_package)
    artifact_contract = (
        global_task.get("artifactContract")
        if isinstance(global_task.get("artifactContract"), dict)
        else {}
    )
    if artifact_contract:
        work_package["constraints"] = _append_policy_text(
            work_package.get("constraints"),
            _artifact_contract_policy(artifact_contract),
        )
        work_package["inputsArtifacts"] = _append_policy_text(
            work_package.get("inputsArtifacts"),
            f"Versioned artifact target: {_text(artifact_contract.get('relativePath'))}",
        )
        work_package["expectedOutput"] = _append_policy_text(
            work_package.get("expectedOutput"),
            _artifact_expected_output_policy(artifact_contract),
        )
    work_package["constraints"] = _append_policy_text(work_package.get("constraints"), MINI_ORIGIN_EXTERNAL_TOOL_POLICY)
    work_package["allowedTools"] = _append_policy_text(work_package.get("allowedTools"), MINI_ORIGIN_EXTERNAL_TOOL_POLICY)
    translations = (
        agent.get("workPackageTranslations")
        if isinstance(agent.get("workPackageTranslations"), dict)
        else {}
    )
    agent_id = _text(agent.get("id") or agent.get("name") or agent.get("role") or f"agent-{index + 1}")
    role = _text(agent.get("role") or agent.get("preset") or agent.get("name") or "agent")
    name = _text(agent.get("name") or role or agent_id)
    previous_output_text = json.dumps(previous_outputs or [], ensure_ascii=False)
    task = {
        "global": global_task,
        "artifactContract": artifact_contract,
        "currentObjective": _text(work_package.get("currentObjective") or global_task.get("title")),
        "instructions": _text(work_package.get("instructions")),
        "constraints": _text(work_package.get("constraints")),
        "expectedOutput": _text(work_package.get("expectedOutput")),
        "inputsArtifacts": _text(work_package.get("inputsArtifacts")),
        "previousOutputs": previous_output_text if previous_outputs else _text(work_package.get("previousOutputs") or previous_output_text),
    }
    if checklist_item:
        task["checklistItem"] = checklist_item
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
        "task": task,
    }


def _task_parts(payload: Dict[str, Any]) -> tuple[str, str, str, str]:
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
    return task_title, task_id, sprint_id, raw_task


def _global_task(payload: Dict[str, Any]) -> Dict[str, Any]:
    task_title, task_id, sprint_id, raw_task = _task_parts(payload)
    global_task = {
        "taskId": task_id,
        "sprintId": sprint_id,
        "project": str(payload.get("project") or "mini-orchestrator").strip(),
        "title": task_title,
        "raw": raw_task,
    }
    artifact_contract = _artifact_contract(payload)
    if artifact_contract:
        global_task["artifactContract"] = artifact_contract
    return global_task


def build_task_checklist(payload: Dict[str, Any]) -> list[Dict[str, Any]]:
    task_title, task_id, _sprint_id, _raw_task = _task_parts(payload)
    raw_items: Any = payload.get("checklist")
    task_value = payload.get("task")
    if raw_items is None and isinstance(task_value, dict):
        raw_items = task_value.get("checklist")
    items: list[Dict[str, Any]] = []
    if isinstance(raw_items, list):
        for index, item in enumerate(raw_items):
            if isinstance(item, dict):
                title = _text(item.get("title") or item.get("text") or item.get("summary")).strip()
                item_id = _text(item.get("id") or item.get("itemId")).strip()
            else:
                title = _text(item).strip()
                item_id = ""
            if title:
                items.append(
                    {
                        "id": item_id or f"item-{index + 1}",
                        "index": index,
                        "title": title,
                        "status": "pending",
                    }
                )
    if items:
        return items
    return [{"id": task_id or "item-1", "index": 0, "title": task_title, "status": "pending"}]


def _chain_preset(payload: Dict[str, Any]) -> Dict[str, Any]:
    return payload.get("chainPreset") if isinstance(payload.get("chainPreset"), dict) else {}


def _chain_summary(chain_preset: Dict[str, Any]) -> Dict[str, Any]:
    return {
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
    }


def _default_agents() -> list[Dict[str, Any]]:
    return [
        {"id": "default-planner", "name": "Planner", "role": "planner", "preset": "planner"},
        {"id": "default-executor", "name": "Executor", "role": "executor", "preset": "executor"},
        {"id": "default-reviewer", "name": "Reviewer", "role": "reviewer", "preset": "reviewer"},
    ]


def build_symphony_intake_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    global_task = _global_task(payload)

    chain_preset = _chain_preset(payload)
    agents = _flow_agents(chain_preset)
    if not agents:
        agents = _default_agents()
    worker_mode = normalize_symphony_worker_mode(payload.get("symphonyWorkerMode"))
    worker_policy = symphony_worker_policy(worker_mode)
    return {
        "schemaVersion": "mini-orchestrator.symphony-intake.v1",
        "approved": True,
        "requestedAt": _utc_now(),
        "requestedBy": "mini-orchestrator",
        "executionMode": "symphony",
        "dispatchStrategy": "one-symphony-agent-per-preset-stage",
        "task": global_task,
        "artifactContract": _artifact_contract(payload),
        "chainPreset": _chain_summary(chain_preset),
        "symphonyWorkerMode": worker_mode,
        "symphonyWorkerPolicy": worker_policy,
        "agentTasks": [_agent_task_from_preset_agent(index, agent, global_task) for index, agent in enumerate(agents)],
        "handoffPolicy": {
            "taskCardIsSingleUserVisibleUnit": True,
            "eachPresetAgentReceivesOwnSettingsAndStageTask": True,
            "previousStageOutputsBecomeNextStageContext": True,
            "chainOwner": "symphony-or-parallel-intake",
        },
    }


def build_symphony_handoff_payload(
    payload: Dict[str, Any],
    *,
    agent_index: int,
    checklist_item: Dict[str, Any] | None = None,
    previous_outputs: list[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    global_task = _global_task(payload)
    chain_preset = _chain_preset(payload)
    agents = _flow_agents(chain_preset) or _default_agents()
    if agent_index < 0 or agent_index >= len(agents):
        raise IndexError(f"Agent index is outside the selected chain: {agent_index}")
    agent = agents[agent_index]
    checklist = build_task_checklist(payload)
    current_item = checklist_item or checklist[0]
    worker_mode = normalize_symphony_worker_mode(payload.get("symphonyWorkerMode"))
    worker_policy = symphony_worker_policy(worker_mode)
    return {
        "schemaVersion": "mini-orchestrator.symphony-intake.v1",
        "approved": True,
        "requestedAt": _utc_now(),
        "requestedBy": "mini-orchestrator",
        "executionMode": "symphony",
        "dispatchStrategy": "mini-owned-single-agent-handoff",
        "task": global_task,
        "artifactContract": _artifact_contract(payload),
        "taskCard": {
            "owner": "mini-orchestrator",
            "status": "running",
            "checklist": checklist,
            "activeChecklistItem": current_item,
        },
        "chainPreset": _chain_summary(chain_preset),
        "chainControl": {
            "owner": "mini-orchestrator",
            "handoffIndex": agent_index,
            "totalAgents": len(agents),
            "currentAgentId": _text(agent.get("id") or agent.get("name") or f"agent-{agent_index + 1}"),
            "previousOutputsCount": len(previous_outputs or []),
            "symphonyWorkerMode": worker_mode,
            "symphonyWorkerPolicy": worker_policy,
        },
        "agentTasks": [
            _agent_task_from_preset_agent(
                agent_index,
                agent,
                global_task,
                checklist_item=current_item,
                previous_outputs=previous_outputs or [],
            )
        ],
        "handoffPolicy": {
            "taskCardIsSingleUserVisibleUnit": True,
            "miniOrchestratorOwnsChecklistAndChain": True,
            "symphonyExecutesOnlyThisAgentStep": True,
            "previousStageOutputsBecomeNextStageContext": True,
            "workerSelectionOwnedBySymphony": True,
        },
    }


def normalize_symphony_worker_mode(value: Any) -> str:
    text = _text(value).lower().replace("_", "-")
    aliases = {
        "debug": "debug-new-worker",
        "debug-symphony": "debug-new-worker",
        "new": "debug-new-worker",
        "new-worker": "debug-new-worker",
        "force-new": "debug-new-worker",
        "force-new-worker": "debug-new-worker",
        "optimal": "optimal-reuse-idle",
        "optimal-symphony": "optimal-reuse-idle",
        "reuse": "optimal-reuse-idle",
        "reuse-idle": "optimal-reuse-idle",
    }
    return aliases.get(text, text if text in {"debug-new-worker", "optimal-reuse-idle"} else "debug-new-worker")


def symphony_worker_policy(mode: str) -> Dict[str, Any]:
    normalized = normalize_symphony_worker_mode(mode)
    if normalized == "optimal-reuse-idle":
        return {
            "mode": "optimal-reuse-idle",
            "reuseIdle": True,
            "newWorkerPerHandoff": False,
            "description": "Symphony may reuse an idle worker when the worker is compatible with the next Mini-owned handoff.",
        }
    return {
        "mode": "debug-new-worker",
        "reuseIdle": False,
        "newWorkerPerHandoff": True,
        "description": "Symphony should create an isolated worker/agent monitor for each Mini-owned handoff so the execution can be inspected step by step.",
    }


def submit_symphony_intake(payload: Dict[str, Any], timeout: float = 10.0) -> Dict[str, Any]:
    runtime = _service_runtime()
    contract_url = _configured_contract_url(runtime)
    contract = _request_json(contract_url, timeout=5.0)
    intake_url = _configured_intake_url(runtime, contract)
    if (
        payload.get("schemaVersion") == "mini-orchestrator.symphony-intake.v1"
        and isinstance(payload.get("agentTasks"), list)
    ):
        intake_payload = payload
    else:
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
        "stale": sum(1 for run in runs if run.get("status") == "stale" or run.get("stale", {}).get("isStale") is True),
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


def _entry_agent_role(entry: Dict[str, Any]) -> str:
    values = " ".join(
        _text(entry.get(key)).casefold()
        for key in ("worker_host", "issue_identifier", "issue_id", "issue_url", "workspace_path")
    )
    for role in ("planner", "executor", "reviewer"):
        if role in values:
            return role
    return ""


def _entry_agent_label(entry: Dict[str, Any]) -> str:
    worker = _text(entry.get("worker_host"))
    if worker:
        return worker
    role = _entry_agent_role(entry)
    if role:
        return role.title()
    return "Symphony worker"


def _entry_agent_model(entry: Dict[str, Any]) -> str | None:
    role = _entry_agent_role(entry)
    if role == "planner":
        return coordinator_model()
    if role == "executor":
        return executor_model()
    if role == "reviewer":
        return reviewer_model()
    return None


def _stage(entry: Dict[str, Any], status: str) -> Dict[str, Any]:
    tokens = _tokens(entry)
    label = _entry_agent_label(entry)
    last_event = _text(entry.get("last_event")) or _text(entry.get("last_message")) or _text(entry.get("error"))
    return {
        "agent": label,
        "label": label,
        "status": status,
        "statusLabel": status.replace("_", " ").title(),
        "startedAt": entry.get("started_at") or entry.get("blocked_at") or entry.get("due_at"),
        "completedAt": entry.get("completed_at") if status == "done" else None,
        "threadId": entry.get("session_id"),
        "turnCount": _int(entry.get("turn_count")),
        "model": _entry_agent_model(entry),
        "tokens": tokens["total"],
        "lastEvent": last_event,
        "output": _text(entry.get("last_message")),
    }


def _run_from_entry(entry: Dict[str, Any], status: str, generated_at: str) -> Dict[str, Any]:
    run_id = _entry_id(entry, status)
    tokens = _tokens(entry)
    agent_label = _entry_agent_label(entry)
    agent_model = _entry_agent_model(entry)
    last_event = (
        _text(entry.get("last_event"))
        or _text(entry.get("last_message"))
        or _text(entry.get("error"))
        or status.replace("_", " ").title()
    )
    updated_at = (
        _text(entry.get("last_event_at"))
        or _text(entry.get("completed_at"))
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
        "currentAgent": agent_label,
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
        "model": agent_model,
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

    for bucket, status in (("running", "running"), ("retrying", "retrying"), ("blocked", "blocked"), ("completed", "done")):
        entries = state.get(bucket)
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
    payload = ensure_artifact_contract(payload, root, reserve=True)
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
            "artifactContract": payload["artifactContract"],
            "artifactPath": payload["artifactContract"]["relativePath"],
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


def _parse_timestamp(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _gateway_submission_identifiers(run: Dict[str, Any]) -> set[str]:
    symphony = run.get("symphony") if isinstance(run.get("symphony"), dict) else {}
    submission = symphony.get("submission") if isinstance(symphony.get("submission"), dict) else {}
    response = submission.get("response") if isinstance(submission.get("response"), dict) else {}
    accepted = response.get("accepted") if isinstance(response.get("accepted"), list) else []
    identifiers: set[str] = set()
    for item in accepted:
        if not isinstance(item, dict):
            continue
        for key in ("identifier", "issue_identifier", "issue_id"):
            value = _text(item.get(key))
            if value:
                identifiers.add(value)
    return identifiers


def _daemon_payload_identifiers(daemon_payload: Dict[str, Any] | None) -> set[str]:
    if not isinstance(daemon_payload, dict):
        return set()
    identifiers: set[str] = set()
    runs = daemon_payload.get("runs") if isinstance(daemon_payload.get("runs"), list) else []
    for run in runs:
        if not isinstance(run, dict):
            continue
        for value in (run.get("runId"), run.get("issue_identifier"), run.get("issue_id")):
            text = _text(value)
            if text:
                identifiers.add(text)
        task = run.get("task") if isinstance(run.get("task"), dict) else {}
        for value in (task.get("taskId"), task.get("raw"), task.get("title")):
            text = _text(value)
            if text:
                identifiers.add(text)
    return identifiers


def _issue_identifiers(issue: Dict[str, Any]) -> set[str]:
    identifiers: set[str] = set()
    for value in (issue.get("issue_identifier"), issue.get("issue_id"), issue.get("issue_url")):
        text = _text(value).strip()
        if text:
            identifiers.add(text)
    return identifiers


def _daemon_runs_by_identifier(daemon_payload: Dict[str, Any] | None) -> dict[str, Dict[str, Any]]:
    if not isinstance(daemon_payload, dict):
        return {}
    indexed: dict[str, Dict[str, Any]] = {}
    runs = daemon_payload.get("runs") if isinstance(daemon_payload.get("runs"), list) else []
    for run in runs:
        if not isinstance(run, dict) or _text(run.get("mode")) == "symphony-daemon-summary":
            continue
        identifiers = set()
        for value in (run.get("runId"), run.get("issue_identifier"), run.get("issue_id")):
            text = _text(value).strip()
            if text:
                identifiers.add(text)
        task = run.get("task") if isinstance(run.get("task"), dict) else {}
        for value in (task.get("taskId"), task.get("raw"), task.get("title")):
            text = _text(value).strip()
            if text:
                identifiers.add(text)
        for identifier in identifiers:
            indexed[identifier] = run
    return indexed


def _mark_gateway_run_stale(run: Dict[str, Any], *, reason: str, now: str) -> Dict[str, Any]:
    run["status"] = "stale"
    run["currentAgent"] = "Symphony intake"
    run["lastEvent"] = "Symphony no longer reports this queued intake as active."
    run["lastError"] = reason
    run["updatedAt"] = now
    run["approval"] = {"required": False, "count": 0}
    event_types = run.get("eventTypes") if isinstance(run.get("eventTypes"), dict) else {}
    event_types["symphony_intake_stale"] = int(event_types.get("symphony_intake_stale") or 0) + 1
    run["eventTypes"] = event_types
    run["stale"] = {
        "isStale": True,
        "reason": reason,
        "lastEventAt": _text(run.get("updatedAt")) or now,
        "thresholdSeconds": 300,
    }
    for stage in run.get("stages") if isinstance(run.get("stages"), list) else []:
        if not isinstance(stage, dict):
            continue
        if _text(stage.get("status")) in {"queued", "running", "planning", "retrying", "waiting_approval", "pending"}:
            stage["status"] = "stale"
            stage["statusLabel"] = "Stale"
            stage["lastEvent"] = "No matching Symphony issue is present in the live daemon state."
    return run


def _reconcile_late_gateway_timeout(
    run: Dict[str, Any],
    daemon_by_identifier: dict[str, Dict[str, Any]],
    *,
    now: str,
) -> tuple[Dict[str, Any], bool]:
    if _text(run.get("status")) != "timeout":
        return run, False
    symphony = run.get("symphony") if isinstance(run.get("symphony"), dict) else {}
    chain = symphony.get("miniOwnedChain") if isinstance(symphony.get("miniOwnedChain"), dict) else {}
    outputs = chain.get("outputs") if isinstance(chain.get("outputs"), list) else []
    steps = chain.get("steps") if isinstance(chain.get("steps"), list) else []
    if not outputs or not daemon_by_identifier:
        return run, False

    changed = False
    for output in outputs:
        if not isinstance(output, dict):
            continue
        if _text(output.get("status")) in {"done", "completed"}:
            continue
        issues = output.get("issues") if isinstance(output.get("issues"), list) else []
        matched_daemon_run = None
        for issue in issues:
            if not isinstance(issue, dict):
                continue
            for identifier in _issue_identifiers(issue):
                candidate = daemon_by_identifier.get(identifier)
                if isinstance(candidate, dict) and _text(candidate.get("status")) == "done":
                    matched_daemon_run = candidate
                    break
            if matched_daemon_run is not None:
                break
        if matched_daemon_run is None:
            continue

        output["status"] = "done"
        output["summary"] = _text(matched_daemon_run.get("lastEvent")) or "turn completed after gateway timeout"
        output["issues"] = [
            {
                "issue_id": matched_daemon_run.get("task", {}).get("taskId")
                if isinstance(matched_daemon_run.get("task"), dict)
                else matched_daemon_run.get("runId"),
                "issue_identifier": matched_daemon_run.get("runId"),
                "status": "completed",
                "completed": {
                    "last_event": matched_daemon_run.get("lastEvent"),
                    "completed_at": matched_daemon_run.get("updatedAt"),
                    "tokens": matched_daemon_run.get("tokens"),
                    "thread_id": matched_daemon_run.get("thread", {}).get("threadId")
                    if isinstance(matched_daemon_run.get("thread"), dict)
                    else None,
                },
            }
        ]
        agent_index = _int(output.get("agentIndex"))
        if agent_index < len(steps) and isinstance(steps[agent_index], dict):
            steps[agent_index]["status"] = "done"
            steps[agent_index]["message"] = "Symphony handoff completed after the gateway timeout."
        stages = run.get("stages") if isinstance(run.get("stages"), list) else []
        if agent_index < len(stages) and isinstance(stages[agent_index], dict):
            stage = stages[agent_index]
            stage["status"] = "done"
            stage["statusLabel"] = "Done"
            stage["lastEvent"] = "Symphony handoff completed after the gateway timeout."
            stage["completedAt"] = matched_daemon_run.get("updatedAt") or now
            daemon_stages = matched_daemon_run.get("stages") if isinstance(matched_daemon_run.get("stages"), list) else []
            if daemon_stages and isinstance(daemon_stages[0], dict):
                stage["threadId"] = daemon_stages[0].get("threadId") or stage.get("threadId")
                stage["turnCount"] = daemon_stages[0].get("turnCount") or stage.get("turnCount")
                stage["tokens"] = daemon_stages[0].get("tokens") or stage.get("tokens")
                stage["model"] = daemon_stages[0].get("model") or stage.get("model")
        changed = True

    if not changed:
        return run, False

    stages = run.get("stages") if isinstance(run.get("stages"), list) else []
    completed_count = sum(1 for stage in stages if isinstance(stage, dict) and _text(stage.get("status")) == "done")
    full_chain_done = bool(stages) and completed_count == len(stages)
    run["status"] = "done" if full_chain_done else "failed"
    run["currentAgent"] = "Mini Orchestrator chain"
    run["lastEvent"] = (
        "All Symphony handoffs completed after the gateway timeout."
        if full_chain_done
        else "A timed-out Symphony handoff completed later, but the Mini-owned chain had already stopped."
    )
    run["lastError"] = "" if full_chain_done else "Rerun the Mini-owned chain to continue the remaining pending stages."
    run["updatedAt"] = now
    run["approval"] = {"required": not full_chain_done, "count": 0}
    run["outputs"] = {
        str(item.get("agentId") or item.get("agentName") or item.get("agentIndex")): item.get("summary")
        for item in outputs
        if isinstance(item, dict)
    }
    chain["status"] = run["status"]
    chain["steps"] = steps
    chain["outputs"] = outputs
    task_card = run.get("taskCard") if isinstance(run.get("taskCard"), dict) else {}
    task_card["owner"] = task_card.get("owner") or "mini-orchestrator"
    task_card["status"] = run["status"]
    task_card["chainOwner"] = task_card.get("chainOwner") or "mini-orchestrator"
    checklist = task_card.get("checklist") if isinstance(task_card.get("checklist"), list) else []
    for item in checklist:
        if isinstance(item, dict):
            item["status"] = "done" if full_chain_done else "failed"
    task_card["checklist"] = checklist
    run["taskCard"] = task_card
    event_types = run.get("eventTypes") if isinstance(run.get("eventTypes"), dict) else {}
    event_types["symphony_late_timeout_reconciled"] = int(event_types.get("symphony_late_timeout_reconciled") or 0) + 1
    run["eventTypes"] = event_types
    return run, True


def _reconcile_gateway_runs_with_daemon(
    root: Path,
    runs: list[Dict[str, Any]],
    daemon_payload: Dict[str, Any] | None,
) -> list[Dict[str, Any]]:
    daemon_identifiers = _daemon_payload_identifiers(daemon_payload)
    if not daemon_identifiers and not isinstance(daemon_payload, dict):
        return runs
    daemon_by_identifier = _daemon_runs_by_identifier(daemon_payload)
    now_dt = datetime.now(timezone.utc)
    now_text = now_dt.isoformat()
    reconciled: list[Dict[str, Any]] = []
    for run in runs:
        late_run, late_changed = _reconcile_late_gateway_timeout(run, daemon_by_identifier, now=now_text)
        if late_changed:
            runtime_store.upsert_json_document(root, "symphony_runs", _text(late_run.get("runId")), late_run)
            reconciled.append(late_run)
            continue
        if _text(run.get("status")) != "queued":
            reconciled.append(run)
            continue
        submission_ids = _gateway_submission_identifiers(run)
        if not submission_ids:
            reconciled.append(run)
            continue
        updated_at = _parse_timestamp(run.get("updatedAt") or run.get("createdAt"))
        if updated_at is not None and (now_dt - updated_at).total_seconds() < 300:
            reconciled.append(run)
            continue
        if submission_ids & daemon_identifiers:
            reconciled.append(run)
            continue
        reason = (
            "Queued Symphony intake is absent from the live daemon state; "
            f"missing accepted issues: {', '.join(sorted(submission_ids))}."
        )
        updated = _mark_gateway_run_stale(run, reason=reason, now=now_text)
        runtime_store.upsert_json_document(root, "symphony_runs", _text(updated.get("runId")), updated)
        reconciled.append(updated)
    return reconciled


def build_local_symphony_gateway_runs(root: Path, daemon_payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
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
    runs = _reconcile_gateway_runs_with_daemon(root, runs, daemon_payload)
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
