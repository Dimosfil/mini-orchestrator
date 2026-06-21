from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json
import re

from . import runtime_store
from .model_defaults import DEFAULT_VISUAL_AGENT_MODEL


ROOT = Path(__file__).resolve().parents[1]
AGENT_CARDS_DIR = ROOT / ".mini_orchestrator" / "agent-cards"
WORKER_PROFILES_DIR = ROOT / ".mini_orchestrator" / "worker-profiles"
DEFAULT_PROJECT_BUILDER_CARD_ID = "project-builder"
DEFAULT_PROJECT_BUILDER_TASK = (
    "Create or improve the runnable project artifact requested by the user. "
    "Choose the artifact name and folder from the task itself, keep repeat runs "
    "versioned under .mini_orchestrator/test-runs/, and include a README with "
    "the original task, entry point, run commands, and verification notes."
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

ALLOWED_SPEEDS = {"fast", "balanced", "careful"}
ALLOWED_REASONING = {"low", "medium", "high"}
ALLOWED_ACCESS_MODES = {"read-only", "workspace-write", "danger-full-access"}


class AgentProfileError(ValueError):
    pass


def default_project_builder_agent_card(root: Path = ROOT) -> dict[str, Any]:
    artifacts_dir = root / ".mini_orchestrator" / "test-runs"
    return {
        "id": DEFAULT_PROJECT_BUILDER_CARD_ID,
        "name": "Project Builder",
        "preset": "executor",
        "role": "Executor",
        "llm": DEFAULT_VISUAL_AGENT_MODEL,
        "speed": "balanced",
        "reasoning": "medium",
        "accessMode": "workspace-write",
        "workPackage": {
            "instructions": (
                "You are the selected visual agent responsible for building and refining "
                "the project artifact requested by the user."
            ),
            "currentObjective": DEFAULT_PROJECT_BUILDER_TASK,
            "inputsArtifacts": (
                f"{_project_path(artifacts_dir, root)}"
            ),
            "constraints": (
                "Do not assume a fixed product domain or artifact type. Derive the domain, "
                "stack, artifact slug, and version folder from the current task. Keep generated "
                "outputs under .mini_orchestrator/test-runs/ unless the user explicitly names "
                "another target."
            ),
            "previousOutputs": "No task-specific artifact is assumed by the default card.",
            "allowedTools": (
                "Read and edit only the selected artifact folder and supporting project-local "
                "docs needed for the task. Run focused syntax, build, or smoke checks when "
                "the artifact defines them."
            ),
            "expectedOutput": (
                "Return a concise report describing what was verified or changed, plus "
                "the artifact path, entry point, and any remaining product gaps."
            ),
        },
    }


def persist_agent_card(card: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    normalized = validate_agent_card(card)
    payload = {
        "card": normalized,
        "updatedAt": _utc_now(),
    }
    runtime_store.upsert_json_document(root, "agent_cards", normalized["id"], payload)
    return {
        "card": normalized,
        "path": runtime_store.runtime_uri("agent-cards", normalized["id"]),
    }


def load_or_create_default_agent_card(root: Path = ROOT) -> dict[str, Any]:
    stored = runtime_store.get_json_document(root, "agent_cards", DEFAULT_PROJECT_BUILDER_CARD_ID)
    if stored is not None:
        card = stored.get("card") if isinstance(stored, dict) else None
        if isinstance(card, dict):
            return validate_agent_card(card)
    path = root / ".mini_orchestrator" / "agent-cards" / f"{DEFAULT_PROJECT_BUILDER_CARD_ID}.json"
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise AgentProfileError(f"Stored agent card is not valid JSON: {path}") from exc
        card = payload.get("card") if isinstance(payload, dict) else None
        if isinstance(card, dict):
            return validate_agent_card(card)
    return persist_agent_card(default_project_builder_agent_card(root), root)["card"]


def validate_agent_card(card: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(card, dict):
        raise AgentProfileError("Agent card must be an object.")

    card_id = _slug(str(card.get("id") or DEFAULT_PROJECT_BUILDER_CARD_ID))
    name = _required_text(card, "name", limit=80)
    role = _required_text(card, "role", limit=80)
    model = _required_text(card, "llm", limit=80)
    if model.casefold() == "rules":
        raise AgentProfileError("Executable agent cards must use a live model, not rules.")

    speed = str(card.get("speed") or "balanced").strip().casefold()
    if speed not in ALLOWED_SPEEDS:
        raise AgentProfileError("Agent field 'speed' must be fast, balanced, or careful.")

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
    task: str = DEFAULT_PROJECT_BUILDER_TASK,
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

    runtime_store.upsert_json_document(root, "worker_profiles", snapshot_id, profile)
    profile["path"] = runtime_store.runtime_uri("worker-profiles", snapshot_id)
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
    return slug[:80] or DEFAULT_PROJECT_BUILDER_CARD_ID


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)
