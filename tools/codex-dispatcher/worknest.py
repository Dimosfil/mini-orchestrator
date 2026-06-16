from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
TASK_MANAGER_CONFIG = ROOT / "tools" / "project-memory" / "task-manager.json"


@dataclass(frozen=True)
class WorkNestTask:
    task_id: str
    sprint_id: str
    project: str
    title: str
    what_to_do: str
    definition_of_done: str


def _json_request(url: str, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"content-type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read().decode("utf-8")
            return json.loads(data) if data else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed with HTTP {exc.code}: {detail}") from exc


def load_task_manager_service_id() -> str:
    if not TASK_MANAGER_CONFIG.exists():
        raise RuntimeError(f"Task manager config is missing: {TASK_MANAGER_CONFIG}")
    data = json.loads(TASK_MANAGER_CONFIG.read_text(encoding="utf-8"))
    service_id = data.get("service_id")
    if not isinstance(service_id, str) or not service_id.strip():
        raise RuntimeError("Task manager config must contain a non-empty service_id.")
    return service_id.strip()


def resolve_config_service_url(explicit: str | None = None) -> str:
    if explicit:
        return explicit.rstrip("/")
    env_url = os.environ.get("GI_CONFIG_SERVICE_URL")
    if env_url:
        return env_url.rstrip("/")
    gi_home = os.environ.get("GENERAL_INSTRUCTIONS_HOME")
    if gi_home:
        config_path = Path(gi_home) / "config" / "gi-main.json"
        if config_path.exists():
            data = json.loads(config_path.read_text(encoding="utf-8"))
            url = data.get("configServiceUrl")
            if isinstance(url, str) and url.strip():
                return url.rstrip("/")
    raise RuntimeError(
        "Config-service URL is not configured. Set GI_CONFIG_SERVICE_URL or GENERAL_INSTRUCTIONS_HOME."
    )


class WorkNestClient:
    def __init__(self, config_service_url: str | None = None) -> None:
        self.config_service_url = resolve_config_service_url(config_service_url)
        self.service_id = load_task_manager_service_id()
        service_url = f"{self.config_service_url}/services/{urllib.parse.quote(self.service_id)}"
        self.service = _json_request(service_url)
        endpoints = self.service.get("endpoints", {})
        self.api_url = endpoints.get("api")
        self.contract_url = endpoints.get("contract")
        if not isinstance(self.api_url, str) or not self.api_url:
            raise RuntimeError(f"Task manager service {self.service_id!r} has no endpoints.api.")
        if not isinstance(self.contract_url, str) or not self.contract_url:
            raise RuntimeError(f"Task manager service {self.service_id!r} has no endpoints.contract.")

    def contract(self) -> dict[str, Any]:
        return _json_request(self.contract_url)

    def next_task(self, project: str) -> WorkNestTask | None:
        url = f"{self.api_url}/next-task?project={urllib.parse.quote(project)}"
        data = _json_request(url)
        task = data.get("task")
        if not isinstance(task, dict):
            return None
        return WorkNestTask(
            task_id=str(task["taskId"]),
            sprint_id=str(task["sprintId"]),
            project=str(task["project"]),
            title=str(task.get("title", "")),
            what_to_do=str(task.get("whatToDo", "")),
            definition_of_done=str(task.get("definitionOfDone", "")),
        )

    def complete_task(
        self,
        task: WorkNestTask,
        summary: str,
        changed_files: list[str],
        checks: list[str],
        blocked: bool = False,
    ) -> dict[str, Any]:
        status = "blocked" if blocked else "done"
        return _json_request(
            f"{self.api_url}/task-completed",
            method="POST",
            payload={
                "project": task.project,
                "sprintId": task.sprint_id,
                "agent": "codex",
                "taskId": task.task_id,
                "status": status,
                "resultStatus": status,
                "outcome": status,
                "summary": summary,
                "changedFiles": changed_files,
                "checks": checks,
            },
        )
