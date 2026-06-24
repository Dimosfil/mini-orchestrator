from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import runtime_store
from .agent_flows import validate_agent_flow


DEFAULT_CHAIN_PRESET_ID = "default-planner-executor-reviewer"
PRESET_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,119}$")


class AgentChainPresetError(ValueError):
    pass


def default_chain_preset() -> dict[str, Any]:
    return {
        "id": DEFAULT_CHAIN_PRESET_ID,
        "name": "Default planner -> executor -> reviewer",
        "flow": {
            "name": "Default planner -> executor -> reviewer",
            "chainPresetId": DEFAULT_CHAIN_PRESET_ID,
            "agents": [
                _agent(
                    "chain-default-planner",
                    "Planner",
                    "planner",
                    "Planner",
                    "gpt-5.5",
                    "balanced",
                    "high",
                    {
                        "instructions": "Turn rough user intent into a scoped plan, assumptions, risks, and a handoff for execution.",
                        "currentObjective": "Clarify what should be built or changed before any file edits happen.",
                        "inputsArtifacts": "User request, selected workflow, relevant project docs, prior approved decisions.",
                        "constraints": "Do not edit files during planning. Keep scope small and ask for approval when needed.",
                        "previousOutputs": "Use prior coordinator summaries only when they are current and task-relevant.",
                        "allowedTools": "Read-only inspection, planning, risk analysis, handoff drafting.",
                        "expectedOutput": "Objective, proposed steps, risks, executor handoff, reviewer checklist.",
                    },
                ),
                _agent(
                    "chain-default-executor",
                    "Executor",
                    "executor",
                    "Executor",
                    "gpt-5.5",
                    "fast",
                    "medium",
                    {
                        "instructions": "Perform bounded technical steps from an approved plan and report the exact result.",
                        "currentObjective": "Implement the approved change with minimal unrelated movement.",
                        "inputsArtifacts": "Approved plan, target files, existing tests, current source code.",
                        "constraints": "Do not expand scope. Preserve user changes. Stop on unsafe ambiguity.",
                        "previousOutputs": "Planner output and any accepted user clarification.",
                        "allowedTools": "Read files, edit scoped files, run focused verification commands.",
                        "expectedOutput": "Changed files, important implementation notes, verification results, blockers if any.",
                    },
                ),
                _agent(
                    "chain-default-reviewer",
                    "Reviewer",
                    "reviewer",
                    "Reviewer",
                    "gpt-5.5",
                    "careful",
                    "high",
                    {
                        "instructions": "Review the implemented result for bugs, regressions, missing tests, and contract drift.",
                        "currentObjective": "Validate whether the executor output satisfies the approved plan.",
                        "inputsArtifacts": "Planner output, executor output, diffs, tests, relevant contracts.",
                        "constraints": "Prioritize concrete findings with file or behavior references.",
                        "previousOutputs": "Planner and executor outputs from this run.",
                        "allowedTools": "Read files, inspect diffs, run focused checks, summarize review findings.",
                        "expectedOutput": "Findings first, residual risk, verification notes, final recommendation.",
                    },
                ),
            ],
            "connections": [
                _connection("chain-default-planner-to-executor", "chain-default-planner", "chain-default-executor"),
                _connection("chain-default-executor-to-reviewer", "chain-default-executor", "chain-default-reviewer"),
            ],
            "nextAgentNumber": 4,
            "presetSettings": {},
        },
        "createdAt": "",
        "updatedAt": "",
        "builtIn": True,
    }


def list_agent_chain_presets(root: Path) -> list[dict[str, Any]]:
    presets = [default_chain_preset()]
    by_id = {DEFAULT_CHAIN_PRESET_ID: presets[0]}
    for item in runtime_store.list_json_documents(root, "agent_chain_presets"):
        try:
            preset = normalize_agent_chain_preset(item)
        except AgentChainPresetError:
            continue
        by_id[preset["id"]] = preset
    presets = list(by_id.values())
    presets.sort(key=lambda item: (item["id"] != DEFAULT_CHAIN_PRESET_ID, str(item.get("name") or "").lower()))
    return presets


def upsert_agent_chain_preset(payload: dict[str, Any], root: Path) -> dict[str, Any]:
    preset = normalize_agent_chain_preset(payload)
    now = _utc_now()
    current = runtime_store.get_json_document(root, "agent_chain_presets", preset["id"])
    preset["createdAt"] = str((current or {}).get("createdAt") or preset.get("createdAt") or now)
    preset["updatedAt"] = now
    preset.pop("builtIn", None)
    runtime_store.upsert_json_document(root, "agent_chain_presets", preset["id"], preset)
    return preset


def import_agent_chain_presets(payload: dict[str, Any], root: Path) -> dict[str, Any]:
    raw_presets = payload.get("presets")
    if not isinstance(raw_presets, list):
        raise AgentChainPresetError("Field 'presets' must be an array.")
    imported: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for index, item in enumerate(raw_presets):
        if not isinstance(item, dict):
            skipped.append({"index": str(index), "reason": "Preset is not an object."})
            continue
        try:
            imported.append(upsert_agent_chain_preset(item, root))
        except AgentChainPresetError as exc:
            skipped.append({"index": str(index), "reason": str(exc)})
    return {"imported": imported, "skipped": skipped}


def delete_agent_chain_preset(preset_id: str, root: Path) -> None:
    normalized_id = _validate_preset_id(preset_id)
    if normalized_id == DEFAULT_CHAIN_PRESET_ID:
        raise AgentChainPresetError("Built-in default chain preset cannot be deleted.")
    if not runtime_store.delete_json_document(root, "agent_chain_presets", normalized_id):
        raise AgentChainPresetError("Agent chain preset was not found.")


def normalize_agent_chain_preset(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AgentChainPresetError("Agent chain preset must be an object.")
    flow = value.get("flow")
    if not isinstance(flow, dict):
        raise AgentChainPresetError("Agent chain preset field 'flow' must be an object.")
    agents = flow.get("agents")
    connections = flow.get("connections")
    if not isinstance(agents, list):
        raise AgentChainPresetError("Agent chain preset flow.agents must be an array.")
    if not isinstance(connections, list):
        raise AgentChainPresetError("Agent chain preset flow.connections must be an array.")
    name = _limited_text(value.get("name") or flow.get("name"), "Agent chain", 80)
    preset_id = _validate_preset_id(value.get("id") or flow.get("chainPresetId") or _slug(name))
    normalized_flow = {
        **flow,
        "name": _limited_text(flow.get("name") or name, name, 120),
        "chainPresetId": preset_id,
        "agents": agents,
        "connections": connections,
        "nextAgentNumber": _positive_int(flow.get("nextAgentNumber"), len(agents) + 1),
        "presetSettings": flow.get("presetSettings") if isinstance(flow.get("presetSettings"), dict) else {},
    }
    validation = validate_agent_flow(
        {
            **normalized_flow,
            "updatedAt": str(value.get("updatedAt") or flow.get("updatedAt") or runtime_store.utc_now()),
        }
    )
    normalized_flow["validation"] = validation
    normalized_flow["validationStatus"] = validation["status"]
    return {
        "id": preset_id,
        "name": name,
        "flow": normalized_flow,
        "validationStatus": validation["status"],
        "createdAt": str(value.get("createdAt") or ""),
        "updatedAt": str(value.get("updatedAt") or ""),
    }


def _agent(
    agent_id: str,
    name: str,
    preset: str,
    role: str,
    llm: str,
    speed: str,
    reasoning: str,
    work_package: dict[str, str],
) -> dict[str, Any]:
    return {
        "id": agent_id,
        "name": name,
        "preset": preset,
        "role": role,
        "llm": llm,
        "speed": speed,
        "reasoning": reasoning,
        "accessMode": "danger-full-access",
        "workPackage": work_package,
    }


def _connection(connection_id: str, from_agent_id: str, to_agent_id: str) -> dict[str, str]:
    return {
        "id": connection_id,
        "fromAgentId": from_agent_id,
        "fromPort": "success",
        "toAgentId": to_agent_id,
        "toPort": "input",
    }


def _validate_preset_id(value: Any) -> str:
    preset_id = str(value or "").strip().lower()
    if not PRESET_ID_PATTERN.match(preset_id):
        raise AgentChainPresetError("Agent chain preset id must be a lowercase slug.")
    return preset_id


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return (slug or "agent-chain")[:100].strip("-") or "agent-chain"


def _limited_text(value: Any, fallback: str, limit: int) -> str:
    text = str(value or "").strip()
    return (text or fallback)[:limit]


def _positive_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
