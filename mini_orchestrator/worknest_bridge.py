from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .service_discovery import ConfigServiceBlocker, load_project_service_runtime_config, resolve_config_service_url


ROOT = Path(__file__).resolve().parents[1]
TASK_MANAGER_CONFIG = ROOT / "tools" / "project-memory" / "task-manager.json"


class WorkNestBridgeError(RuntimeError):
    pass


@dataclass(frozen=True)
class WorkNestTask:
    task_id: str
    sprint_id: str
    project: str
    title: str
    what_to_do: str
    definition_of_done: str


def load_task_manager_service_id(root: Path = ROOT) -> str:
    config_path = root / "tools" / "project-memory" / "task-manager.json"
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WorkNestBridgeError(f"Task-manager config is missing: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise WorkNestBridgeError(f"Task-manager config is not valid JSON: {config_path}") from exc
    service_id = str(payload.get("service_id") or "").strip()
    if not service_id:
        raise WorkNestBridgeError("Task-manager config must contain service_id.")
    return service_id


class WorkNestLifecycleBridge:
    def __init__(
        self,
        *,
        root: Path = ROOT,
        config_service_url: str | None = None,
        service_id: str | None = None,
    ) -> None:
        self.root = root
        self.service_id = service_id or load_task_manager_service_id(root)
        self.config_service_url = (config_service_url or self._resolve_config_service_url()).rstrip("/")
        record = _json_request(f"{self.config_service_url}/services/{urllib.parse.quote(self.service_id)}")
        endpoints = record.get("endpoints") if isinstance(record.get("endpoints"), dict) else {}
        self.api_url = str(endpoints.get("api") or "").rstrip("/")
        self.contract_url = str(endpoints.get("contract") or "")
        if not self.api_url:
            raise WorkNestBridgeError(f"Task-manager service {self.service_id!r} has no endpoints.api.")
        if not self.contract_url:
            raise WorkNestBridgeError(f"Task-manager service {self.service_id!r} has no endpoints.contract.")
        capabilities = record.get("capabilities") if isinstance(record.get("capabilities"), list) else []
        self.capabilities = {str(item) for item in capabilities}

    def _resolve_config_service_url(self) -> str:
        try:
            runtime_config = load_project_service_runtime_config()
            return resolve_config_service_url(runtime_config)
        except ConfigServiceBlocker as exc:
            raise WorkNestBridgeError(str(exc)) from exc

    def contract(self) -> dict[str, Any]:
        return _json_request(self.contract_url)

    def verify_contract(self, *, require_next_task: bool = False, require_completion: bool = False) -> dict[str, Any]:
        contract = self.contract()
        external_agents = " ".join(contract.get("taskMovementPolicy", {}).get("externalAgents", []))
        if require_next_task and "next-task" not in external_agents:
            raise WorkNestBridgeError("WorkNest contract does not document next-task for external agents.")
        if require_completion and "task-completed" not in external_agents:
            raise WorkNestBridgeError("WorkNest contract does not document task-completed for external agents.")
        if require_completion and "task-completion" not in self.capabilities:
            raise WorkNestBridgeError("WorkNest service does not advertise task-completion capability.")
        return contract

    def claim_next_task(self, project: str) -> WorkNestTask | None:
        self.verify_contract(require_next_task=True)
        data = _json_request(f"{self.api_url}/next-task?project={urllib.parse.quote(project)}")
        task = data.get("task")
        if not isinstance(task, dict):
            return None
        return WorkNestTask(
            task_id=str(task.get("taskId") or ""),
            sprint_id=str(task.get("sprintId") or ""),
            project=str(task.get("project") or project),
            title=str(task.get("title") or ""),
            what_to_do=str(task.get("whatToDo") or ""),
            definition_of_done=str(task.get("definitionOfDone") or ""),
        )

    def complete_task(
        self,
        *,
        task_id: str,
        sprint_id: str,
        project: str,
        status: str,
        summary: str,
        changed_files: list[str] | None = None,
        checks: list[str] | None = None,
    ) -> dict[str, Any]:
        terminal = status.strip().lower()
        if terminal not in {"done", "blocked"}:
            raise WorkNestBridgeError("WorkNest completion status must be 'done' or 'blocked'.")
        if not task_id.strip() or not sprint_id.strip() or not project.strip():
            raise WorkNestBridgeError("taskId, sprintId, and project are required for WorkNest completion.")
        self.verify_contract(require_completion=True)
        return _json_request(
            f"{self.api_url}/task-completed",
            method="POST",
            payload={
                "project": project,
                "sprintId": sprint_id,
                "agent": "codex",
                "taskId": task_id,
                "status": terminal,
                "resultStatus": terminal,
                "outcome": terminal,
                "summary": summary,
                "changedFiles": changed_files or [],
                "checks": checks or [],
            },
        )


def _json_request(url: str, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"content-type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        data = response.read().decode("utf-8")
    if not data:
        return {}
    decoded = json.loads(data)
    if not isinstance(decoded, dict):
        raise WorkNestBridgeError("WorkNest response must be a JSON object.")
    return decoded
