from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import re

from mini_orchestrator.model_defaults import coordinator_model, executor_model, reviewer_model

from models import Worker


WORK_PACKAGE_LABELS = (
    ("Role/instructions", "instructions"),
    ("Current objective", "currentObjective"),
    ("Inputs/artifacts", "inputsArtifacts"),
    ("Constraints", "constraints"),
    ("Previous agent outputs", "previousOutputs"),
    ("Allowed tools/actions", "allowedTools"),
    ("Expected output format", "expectedOutput"),
)

ROLE_KEYS = {
    "planner": "planner",
    "plan": "planner",
    "executor": "executor",
    "execute": "executor",
    "reviewer": "reviewer",
    "review": "reviewer",
}

def default_workers(root: Path) -> list[Worker]:
    coordinator_model_value = coordinator_model()
    executor_model_value = executor_model()
    reviewer_model_value = reviewer_model()
    return [
        Worker("planner", coordinator_model_value, "high", root / ".codex" / "agents" / "planner.toml"),
        Worker("executor", executor_model_value, "medium", root / ".codex" / "agents" / "executor.toml"),
        Worker("reviewer", reviewer_model_value, "high", root / ".codex" / "agents" / "reviewer.toml"),
    ]


def workers_from_chain_preset_file(path: Path, root: Path) -> list[Worker]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("Chain preset file must contain a JSON object.")
    return workers_from_chain_preset(payload, root)


def workers_from_chain_preset(preset: dict[str, Any], root: Path) -> list[Worker]:
    flow = preset.get("flow")
    if not isinstance(flow, dict):
        raise ValueError("Chain preset must include a flow object.")
    agents = flow.get("agents")
    if not isinstance(agents, list) or not agents:
        raise ValueError("Chain preset flow must include at least one agent.")
    connections = flow.get("connections") if isinstance(flow.get("connections"), list) else []
    agent_map = {str(agent.get("id") or "").strip(): agent for agent in agents if isinstance(agent, dict)}
    ordered_ids = _ordered_agent_ids(agents, connections)
    workers: list[Worker] = []
    used_names: set[str] = set()
    for agent_id in ordered_ids:
        agent = agent_map.get(agent_id)
        if not agent:
            continue
        worker_name = _worker_name(agent, used_names)
        model = _agent_model(agent)
        if model.casefold() == "rules":
            raise ValueError(f"Chain agent {agent.get('name') or agent_id!r} uses rules fallback, not a live model.")
        reasoning = _reasoning(agent.get("reasoning"))
        access_mode = _access_mode(agent.get("accessMode"))
        workers.append(
            Worker(
                worker_name,
                model,
                reasoning,
                root / ".codex" / "agents" / "visual-agent.toml",
                access_mode=access_mode,
                source_agent_id=agent_id,
                instructions_text=_agent_instructions(agent, worker_name),
            )
        )

    if not workers:
        raise ValueError("Chain preset did not produce executable workers.")
    return workers


def _ordered_agent_ids(agents: list[Any], connections: list[Any]) -> list[str]:
    agent_ids = [str(agent.get("id") or "").strip() for agent in agents if isinstance(agent, dict)]
    agent_ids = [agent_id for agent_id in agent_ids if agent_id]
    incoming = {agent_id: 0 for agent_id in agent_ids}
    outgoing = {agent_id: [] for agent_id in agent_ids}
    for connection in connections:
        if not isinstance(connection, dict):
            continue
        source = str(connection.get("fromAgentId") or "").strip()
        target = str(connection.get("toAgentId") or "").strip()
        if source in outgoing and target in incoming:
            outgoing[source].append(target)
            incoming[target] += 1
    ready = [agent_id for agent_id in agent_ids if incoming.get(agent_id) == 0]
    ordered: list[str] = []
    while ready:
        current = ready.pop(0)
        if current in ordered:
            continue
        ordered.append(current)
        for target in outgoing.get(current, []):
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)
    return ordered if len(ordered) == len(agent_ids) else agent_ids


def _worker_name(agent: dict[str, Any], used_names: set[str]) -> str:
    role_key = _role_key(agent.get("role") or agent.get("preset") or agent.get("name"))
    base = role_key or _slug(str(agent.get("name") or agent.get("id") or "agent"))
    candidate = base
    index = 2
    while candidate in used_names:
        candidate = f"{base}-{index}"
        index += 1
    used_names.add(candidate)
    return candidate


def _role_key(value: Any) -> str:
    normalized = str(value or "").strip().casefold()
    return ROLE_KEYS.get(normalized, "")


def _agent_model(agent: dict[str, Any]) -> str:
    model = str(agent.get("llm") or "").strip()
    if model:
        return model
    name = str(agent.get("name") or agent.get("id") or agent.get("role") or "agent").strip()
    raise ValueError(f"Chain agent {name!r} is missing an explicit llm setting.")


def _reasoning(value: Any) -> str:
    normalized = str(value or "").strip().casefold().replace("very high", "high")
    if normalized == "very_high":
        return "high"
    return normalized if normalized in {"low", "medium", "high"} else "medium"


def _access_mode(value: Any) -> str:
    mode = str(value or "").strip()
    if mode in {"danger-full-access", "workspace-write", "read-only"}:
        return mode
    return "workspace-write"


def _agent_instructions(agent: dict[str, Any], worker_name: str) -> str:
    work_package = agent.get("workPackage") if isinstance(agent.get("workPackage"), dict) else {}
    lines = [
        "This worker profile was loaded from the selected mini-orchestrator agent chain preset.",
        "",
        f"Worker role: {worker_name}",
        f"Agent name: {str(agent.get('name') or worker_name).strip()}",
        f"Agent role: {str(agent.get('role') or '').strip()}",
        f"Preset: {str(agent.get('preset') or '').strip()}",
        f"Selected model: {_agent_model(agent)}",
        f"Reasoning: {_reasoning(agent.get('reasoning'))}",
        f"Access mode: {_access_mode(agent.get('accessMode'))}",
        "",
        "Work package:",
    ]
    for label, key in WORK_PACKAGE_LABELS:
        value = str(work_package.get(key) or "").strip()
        if value:
            lines.append(f"- {label}: {value}")
    if lines[-1] == "Work package:":
        lines.append("- No custom work package fields were supplied.")
    return "\n".join(lines) + "\n"


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().casefold()).strip("-")
    return slug[:80] or "agent"
