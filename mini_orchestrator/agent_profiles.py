from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json
import re


ROOT = Path(__file__).resolve().parents[1]
AGENT_CARDS_DIR = ROOT / ".mini_orchestrator" / "agent-cards"
WORKER_PROFILES_DIR = ROOT / ".mini_orchestrator" / "worker-profiles"
DEFAULT_DENTAL_CRM_CARD_ID = "dental-crm-builder"
DEFAULT_DENTAL_CRM_TASK = (
    "Create or improve a runnable dental CRM demo for a dentistry clinic. "
    "The demo should be directly openable as an HTML file and show patient cards, "
    "appointments, treatment statuses, and admin tasks on a Kanban board. "
    "Keep the work scoped to .mini_orchestrator/test-runs/dental-crm-demo/."
)

WORK_PACKAGE_KEYS = (
    "instructions",
    "currentObjective",
    "inputsArtifacts",
    "constraints",
    "previousOutputs",
    "allowedTools",
    "expectedOutput",
)

ALLOWED_SPEEDS = {"fast", "balanced", "thorough"}
ALLOWED_REASONING = {"low", "medium", "high"}
ALLOWED_ACCESS_MODES = {"read-only", "workspace-write", "danger-full-access"}


class AgentProfileError(ValueError):
    pass


def default_dental_crm_agent_card(root: Path = ROOT) -> dict[str, Any]:
    demo_dir = root / ".mini_orchestrator" / "test-runs" / "dental-crm-demo"
    return {
        "id": DEFAULT_DENTAL_CRM_CARD_ID,
        "name": "Dental CRM Builder",
        "preset": "executor",
        "role": "Executor",
        "llm": "gpt-5.4",
        "speed": "balanced",
        "reasoning": "medium",
        "accessMode": "workspace-write",
        "workPackage": {
            "instructions": (
                "You are the selected visual agent responsible for building and refining "
                "the standalone dental clinic CRM demo."
            ),
            "currentObjective": DEFAULT_DENTAL_CRM_TASK,
            "inputsArtifacts": (
                f"{_project_path(demo_dir / 'index.html', root)}\n"
                f"{_project_path(demo_dir / 'README.md', root)}"
            ),
            "constraints": (
                "Keep edits scoped to .mini_orchestrator/test-runs/dental-crm-demo/. "
                "Do not edit unrelated project files. The demo must work by opening "
                "index.html directly in a browser, without a server."
            ),
            "previousOutputs": (
                "A first dental CRM demo already exists with patient cards, appointments, "
                "treatment progress, and an admin-task Kanban."
            ),
            "allowedTools": (
                "Read and edit files under the dental CRM demo folder. Run focused syntax "
                "or smoke checks for the demo. Summarize any changes."
            ),
            "expectedOutput": (
                "Return a concise report describing what was verified or changed, plus "
                "the runnable demo path and any remaining product gaps."
            ),
        },
    }


def persist_agent_card(card: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    normalized = validate_agent_card(card)
    cards_dir = root / ".mini_orchestrator" / "agent-cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    path = cards_dir / f"{normalized['id']}.json"
    payload = {
        "card": normalized,
        "updatedAt": _utc_now(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "card": normalized,
        "path": _project_path(path, root),
    }


def load_or_create_default_agent_card(root: Path = ROOT) -> dict[str, Any]:
    path = root / ".mini_orchestrator" / "agent-cards" / f"{DEFAULT_DENTAL_CRM_CARD_ID}.json"
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise AgentProfileError(f"Stored agent card is not valid JSON: {path}") from exc
        card = payload.get("card") if isinstance(payload, dict) else None
        if isinstance(card, dict):
            return validate_agent_card(card)
    return persist_agent_card(default_dental_crm_agent_card(root), root)["card"]


def validate_agent_card(card: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(card, dict):
        raise AgentProfileError("Agent card must be an object.")

    card_id = _slug(str(card.get("id") or DEFAULT_DENTAL_CRM_CARD_ID))
    name = _required_text(card, "name", limit=80)
    role = _required_text(card, "role", limit=80)
    model = _required_text(card, "llm", limit=80)
    if model.casefold() == "rules":
        raise AgentProfileError("Executable agent cards must use a live model, not rules.")

    speed = str(card.get("speed") or "balanced").strip().casefold()
    if speed not in ALLOWED_SPEEDS:
        raise AgentProfileError("Agent field 'speed' must be fast, balanced, or thorough.")

    reasoning = str(card.get("reasoning") or "medium").strip().casefold().replace("very high", "high")
    if reasoning not in ALLOWED_REASONING:
        raise AgentProfileError("Agent field 'reasoning' must be low, medium, or high.")

    access_mode = str(card.get("accessMode") or "workspace-write").strip()
    if access_mode not in ALLOWED_ACCESS_MODES:
        raise AgentProfileError(
            "Agent field 'accessMode' must be read-only, workspace-write, or danger-full-access."
        )

    work_package_value = card.get("workPackage", {})
    work_package = work_package_value if isinstance(work_package_value, dict) else {}
    normalized_work_package = {
        key: str(work_package.get(key) or "").strip()[:2000]
        for key in WORK_PACKAGE_KEYS
        if str(work_package.get(key) or "").strip()
    }
    if not normalized_work_package.get("currentObjective"):
        raise AgentProfileError("Agent workPackage.currentObjective is required.")
    if not normalized_work_package.get("constraints"):
        raise AgentProfileError("Agent workPackage.constraints is required.")

    return {
        "id": card_id,
        "name": name,
        "preset": str(card.get("preset") or "agent").strip()[:40] or "agent",
        "role": role,
        "llm": model,
        "speed": speed,
        "reasoning": reasoning,
        "accessMode": access_mode,
        "workPackage": normalized_work_package,
    }


def compile_worker_profile(
    card: dict[str, Any],
    task: str = DEFAULT_DENTAL_CRM_TASK,
    root: Path = ROOT,
) -> dict[str, Any]:
    normalized = validate_agent_card(card)
    selected_task = str(task or "").strip()
    if not selected_task:
        raise AgentProfileError("Task is required.")

    hash_payload = {
        "card": normalized,
        "task": selected_task,
        "schema": "mini-orchestrator.visual-worker-profile.v1",
    }
    snapshot_hash = hashlib.sha256(
        json.dumps(hash_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    snapshot_id = f"worker-profile-{normalized['id']}-{snapshot_hash}"
    profile = {
        "schema": "mini-orchestrator.visual-worker-profile.v1",
        "snapshotId": snapshot_id,
        "sourceCardId": normalized["id"],
        "compiledAt": _utc_now(),
        "immutable": True,
        "task": selected_task,
        "agent": normalized,
        "runtime": {
            "kind": "codex-app-server",
            "worker": "visual-agent",
            "model": normalized["llm"],
            "reasoning": normalized["reasoning"],
            "accessMode": normalized["accessMode"],
        },
    }

    profiles_dir = root / ".mini_orchestrator" / "worker-profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    path = profiles_dir / f"{snapshot_id}.json"
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    profile["path"] = _project_path(path, root)
    return profile


def visual_agent_task_prompt(profile: dict[str, Any]) -> str:
    agent = profile.get("agent") if isinstance(profile.get("agent"), dict) else {}
    work_package = agent.get("workPackage") if isinstance(agent.get("workPackage"), dict) else {}
    lines = [
        "Execute this task as the selected compiled visual agent card.",
        "",
        f"Worker profile snapshot: {profile.get('snapshotId')}",
        f"Agent name: {agent.get('name')}",
        f"Agent role: {agent.get('role')}",
        f"Model: {agent.get('llm')}",
        f"Reasoning: {agent.get('reasoning')}",
        f"Access mode: {agent.get('accessMode')}",
        "",
        "Task:",
        str(profile.get("task") or ""),
        "",
        "Work package:",
    ]
    for key in WORK_PACKAGE_KEYS:
        value = str(work_package.get(key) or "").strip()
        if value:
            lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "Operate only within the stated constraints. If no file changes are needed, verify the target and report that.",
        ]
    )
    return "\n".join(lines)


def _required_text(card: dict[str, Any], key: str, limit: int) -> str:
    value = str(card.get(key) or "").strip()
    if not value:
        raise AgentProfileError(f"Agent field '{key}' is required.")
    return value[:limit]


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().casefold()).strip("-")
    return slug[:80] or DEFAULT_DENTAL_CRM_CARD_ID


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)
