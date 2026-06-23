from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import runtime_store


FLOW_DIR = ".mini_orchestrator/agent-flows"
MANIFEST_DIR = ".mini_orchestrator/agent-flow-manifests"
FLOW_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")
SUPPORTED_ACCESS_MODES = {"danger-full-access", "workspace-write", "read-only"}
SUPPORTED_REASONING = {"low", "medium", "high", "very_high"}
SUPPORTED_ROLES = {"Agent", "Custom", "Executor", "Planner", "PM", "QA", "Reviewer"}
DEFAULT_MAX_LOOP_ITERATIONS = 3
DEFAULT_MAX_CHECKLIST_ATTEMPTS = 3
WORK_PACKAGE_FIELDS = {
    "allowedTools",
    "constraints",
    "currentObjective",
    "expectedOutput",
    "inputsArtifacts",
    "instructions",
    "previousOutputs",
}


class AgentFlowError(ValueError):
    pass


def list_agent_flows(root: Path) -> list[dict[str, Any]]:
    flows = [_summary(flow) for flow in runtime_store.list_json_documents(root, "agent_flows")]
    seen = {str(flow.get("id") or "") for flow in flows}
    flow_dir = _flow_dir(root)
    if flow_dir.exists():
        for path in sorted(flow_dir.glob("*.json")):
            try:
                flow = _read_flow_path(path)
            except AgentFlowError:
                continue
            if str(flow.get("id") or "") in seen:
                continue
            flows.append(_summary(flow))
    flows.sort(key=lambda item: str(item.get("updatedAt") or ""), reverse=True)
    return flows


def create_agent_flow(payload: dict[str, Any], root: Path) -> dict[str, Any]:
    now = _utc_now()
    draft = _payload_flow(payload)
    flow_id = _unique_flow_id(root, str(draft.get("name") or "agent-flow"))
    flow = _normalize_flow(draft, now=now, flow_id=flow_id, version=1, created_at=now)
    _write_flow(root, flow)
    return flow


def read_agent_flow(flow_id: str, root: Path) -> dict[str, Any]:
    normalized_id = _validate_flow_id(flow_id)
    stored = runtime_store.get_json_document(root, "agent_flows", normalized_id)
    if stored is not None:
        return stored
    return _read_flow_path(_flow_path(root, normalized_id))


def update_agent_flow(flow_id: str, payload: dict[str, Any], root: Path) -> dict[str, Any]:
    current = read_agent_flow(flow_id, root)
    draft = _payload_flow(payload)
    now = _utc_now()
    version = int(current.get("version") or 1) + 1
    flow = _normalize_flow(
        draft,
        now=now,
        flow_id=flow_id,
        version=version,
        created_at=str(current.get("createdAt") or now),
    )
    _write_flow(root, flow)
    return flow


def validate_saved_agent_flow(
    flow_id: str,
    root: Path,
    *,
    selected_start_agent_id: str | None = None,
) -> dict[str, Any]:
    flow = read_agent_flow(flow_id, root)
    validation = validate_agent_flow(flow, selected_start_agent_id=selected_start_agent_id)
    flow["validation"] = validation
    flow["validationStatus"] = validation["status"]
    _write_flow(root, flow)
    return validation


def validate_agent_flow(
    flow: dict[str, Any],
    *,
    selected_start_agent_id: str | None = None,
) -> dict[str, Any]:
    return _validate_graph(flow, selected_start_agent_id=selected_start_agent_id)


def compile_saved_agent_flow(flow_id: str, root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    approval = payload.get("approval") if isinstance(payload.get("approval"), dict) else {}
    if approval.get("approved") is not True:
        raise AgentFlowError("Compile requires approval.approved=true.")
    flow = read_agent_flow(flow_id, root)
    selected_start_agent_id = str(payload.get("selectedStartAgentId") or "").strip() or None
    validation = validate_agent_flow(flow, selected_start_agent_id=selected_start_agent_id)
    if not validation["valid"]:
        raise AgentFlowError("Flow must validate before compile.")

    compiled_at = _utc_now()
    approval_id = str(approval.get("approvalId") or f"approval-{uuid.uuid4().hex[:12]}").strip()
    manifest_id = f"manifest-{uuid.uuid4().hex[:12]}"
    profile_snapshots = [
        _compile_profile_snapshot(flow, agent, compiled_at=compiled_at, approval_id=approval_id)
        for agent in flow.get("agents", [])
    ]
    graph = _compile_graph(flow, validation)
    manifest = {
        "schemaVersion": 1,
        "manifestId": manifest_id,
        "flowId": flow["id"],
        "flowVersion": flow["version"],
        "compiledAt": compiled_at,
        "approval": {
            "approvalId": approval_id,
            "approved": True,
            "approvedBy": str(approval.get("approvedBy") or "user").strip()[:120],
            "approvedAt": str(approval.get("approvedAt") or compiled_at),
        },
        "runContext": _compile_run_context(payload.get("runContext")),
        "runtimePolicy": {
            "workspaceRootPolicy": "project-root",
            "networkAccess": True,
            "maxTurnsPerNode": _positive_int(payload.get("maxTurnsPerNode"), 12),
        },
        "profileSnapshots": profile_snapshots,
        "graph": graph,
        "sourceFlow": {
            "id": flow["id"],
            "name": flow["name"],
            "version": flow["version"],
            "validationStatus": validation["status"],
        },
    }
    runtime_store.upsert_json_document(root, "agent_flow_manifests", manifest_id, manifest)
    manifest["path"] = runtime_store.runtime_uri("agent-flow-manifests", manifest_id)
    return manifest


def read_compiled_manifest(manifest_id: str, root: Path) -> dict[str, Any]:
    normalized_id = _validate_flow_id(manifest_id)
    stored = runtime_store.get_json_document(root, "agent_flow_manifests", normalized_id)
    if stored is not None:
        stored["path"] = runtime_store.runtime_uri("agent-flow-manifests", normalized_id)
        return stored
    path = _manifest_path(root, manifest_id)
    if not path.exists():
        raise AgentFlowError("Run manifest was not found.")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AgentFlowError("Run manifest is not an object.")
    data["path"] = _project_path(path, root)
    return data


def _payload_flow(payload: dict[str, Any]) -> dict[str, Any]:
    flow = payload.get("flow", payload)
    if not isinstance(flow, dict):
        raise AgentFlowError("Flow payload must be an object.")
    return flow


def _normalize_flow(
    flow: dict[str, Any],
    *,
    now: str,
    flow_id: str,
    version: int,
    created_at: str,
) -> dict[str, Any]:
    name = _limited_text(flow.get("name"), "Agent flow", 120)
    agents = flow.get("agents")
    connections = flow.get("connections")
    if not isinstance(agents, list):
        raise AgentFlowError("Flow field 'agents' must be an array.")
    if not isinstance(connections, list):
        raise AgentFlowError("Flow field 'connections' must be an array.")

    normalized = {
        "id": _validate_flow_id(flow_id),
        "name": name,
        "version": version,
        "agents": [_normalize_agent(agent, index) for index, agent in enumerate(agents)],
        "connections": [_normalize_connection(connection, index) for index, connection in enumerate(connections)],
        "presetSettings": flow.get("presetSettings") if isinstance(flow.get("presetSettings"), dict) else {},
        "chainPresetId": str(flow.get("chainPresetId") or "").strip()[:120],
        "nextAgentNumber": _positive_int(flow.get("nextAgentNumber"), len(agents) + 1),
        "createdAt": created_at,
        "updatedAt": now,
    }
    normalized["validation"] = validate_agent_flow(normalized)
    normalized["validationStatus"] = normalized["validation"]["status"]
    return normalized


def _normalize_agent(agent: Any, index: int) -> dict[str, Any]:
    if not isinstance(agent, dict):
        raise AgentFlowError(f"Agent at index {index} must be an object.")
    agent_id = _limited_text(agent.get("id"), f"agent-{index + 1}", 120)
    name = _limited_text(agent.get("name"), f"Agent {index + 1}", 120)
    return {
        **agent,
        "id": agent_id,
        "name": name,
        "preset": _limited_text(agent.get("preset"), "agent", 80),
        "role": _limited_text(agent.get("role"), "Agent", 80),
        "x": _number(agent.get("x"), 0),
        "y": _number(agent.get("y"), 0),
    }


def _normalize_connection(connection: Any, index: int) -> dict[str, Any]:
    if not isinstance(connection, dict):
        raise AgentFlowError(f"Connection at index {index} must be an object.")
    from_port = "failure" if connection.get("fromPort") == "failure" else "success"
    return {
        **connection,
        "id": _limited_text(connection.get("id"), f"connection-{index + 1}", 120),
        "fromAgentId": _limited_text(connection.get("fromAgentId"), "", 120),
        "toAgentId": _limited_text(connection.get("toAgentId"), "", 120),
        "fromPort": from_port,
        "toPort": "input",
    }


def _validate_graph(
    flow: dict[str, Any],
    *,
    selected_start_agent_id: str | None = None,
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    agent_ids: set[str] = set()
    agents = flow.get("agents") if isinstance(flow.get("agents"), list) else []
    connections = flow.get("connections") if isinstance(flow.get("connections"), list) else []

    if not agents:
        errors.append(_issue("no_agents", "Flow must contain at least one agent.", "agents"))

    for index, agent in enumerate(agents):
        agent_id = str(agent.get("id") or "")
        if not agent_id:
            errors.append(_issue("missing_agent_id", "Agent id is required.", f"agents[{index}].id"))
        if agent_id in agent_ids:
            errors.append(_issue("duplicate_agent_id", f"Duplicate agent id: {agent_id}", f"agents[{index}].id"))
        agent_ids.add(agent_id)
        if not str(agent.get("name") or "").strip():
            errors.append(_issue("missing_agent_name", "Agent name is required.", f"agents[{index}].name"))
        role = str(agent.get("role") or "").strip()
        if role not in SUPPORTED_ROLES:
            errors.append(_issue("unsupported_role", f"Unsupported role: {role or '(empty)'}", f"agents[{index}].role"))
        access_mode = str(agent.get("accessMode") or "").strip()
        if access_mode not in SUPPORTED_ACCESS_MODES:
            errors.append(
                _issue("unsupported_access_mode", f"Unsupported access mode: {access_mode or '(empty)'}", f"agents[{index}].accessMode")
            )
        model = str(agent.get("llm") or "").strip()
        if not model:
            errors.append(_issue("missing_model", "Agent model is required.", f"agents[{index}].llm"))
        elif model == "rules":
            errors.append(_issue("rules_model_not_executable", "Rules fallback is not executable by the daemon.", f"agents[{index}].llm"))
        reasoning = str(agent.get("reasoning") or "").strip()
        if reasoning not in SUPPORTED_REASONING:
            errors.append(
                _issue("unsupported_reasoning", f"Unsupported reasoning setting: {reasoning or '(empty)'}", f"agents[{index}].reasoning")
            )
        work_package = agent.get("workPackage")
        if not isinstance(work_package, dict):
            errors.append(_issue("missing_work_package", "Agent workPackage is required.", f"agents[{index}].workPackage"))
        else:
            for field in sorted(WORK_PACKAGE_FIELDS):
                if not str(work_package.get(field) or "").strip():
                    errors.append(
                        _issue(
                            "missing_work_package_field",
                            f"Work package field is required: {field}",
                            f"agents[{index}].workPackage.{field}",
                        )
                    )

    connection_keys: set[tuple[str, str, str]] = set()
    graph: dict[str, list[str]] = {agent_id: [] for agent_id in agent_ids}
    success_graph: dict[str, list[str]] = {agent_id: [] for agent_id in agent_ids}
    rework_loops: list[dict[str, Any]] = []
    incoming_counts: dict[str, int] = {agent_id: 0 for agent_id in agent_ids}
    for index, connection in enumerate(connections):
        from_agent = str(connection.get("fromAgentId") or "")
        to_agent = str(connection.get("toAgentId") or "")
        from_port = str(connection.get("fromPort") or "success")
        if from_agent not in agent_ids:
            errors.append(
                _issue("missing_from_agent", f"Connection source is missing: {from_agent}", f"connections[{index}].fromAgentId")
            )
        if to_agent not in agent_ids:
            errors.append(_issue("missing_to_agent", f"Connection target is missing: {to_agent}", f"connections[{index}].toAgentId"))
        if from_agent and from_agent == to_agent:
            errors.append(_issue("self_connection", f"Connection loops to the same agent: {from_agent}", f"connections[{index}]"))
        key = (from_agent, from_port, to_agent)
        if key in connection_keys:
            errors.append(_issue("duplicate_connection", "Duplicate connection branch.", f"connections[{index}]"))
        connection_keys.add(key)
        if from_agent in agent_ids and to_agent in agent_ids and from_agent != to_agent:
            graph[from_agent].append(to_agent)
            if from_port == "success":
                success_graph[from_agent].append(to_agent)
            elif from_port == "failure":
                rework_loops.append(
                    {
                        "fromAgentId": from_agent,
                        "toAgentId": to_agent,
                        "fromPort": "failure",
                        "maxIterations": _loop_max_iterations(flow),
                    }
                )
            if from_port == "success":
                incoming_counts[to_agent] += 1

    start_node_candidates = [
        {"agentId": agent_id, "name": _agent_name(agents, agent_id)}
        for agent_id, count in incoming_counts.items()
        if count == 0 and agent_id
    ]
    selected = str(selected_start_agent_id or flow.get("selectedStartAgentId") or "").strip()
    if selected:
        if selected not in agent_ids:
            errors.append(_issue("missing_selected_start_node", f"Selected start node is missing: {selected}", "selectedStartAgentId"))
    elif len(start_node_candidates) != 1:
        errors.append(
            _issue(
                "ambiguous_start_node",
                "Flow must have exactly one start node or an explicit selected start node.",
                "selectedStartAgentId",
            )
        )

    success_cycle = _find_cycle(success_graph)
    if success_cycle:
        if not _cycle_has_role(success_cycle, agents, "PM"):
            errors.append(_issue("cycle_detected", f"Flow contains a success-path cycle: {' -> '.join(success_cycle)}", "connections"))

    if not connections and len(agents) > 1:
        warnings.append(_issue("no_connections", "Multi-agent flow has no connections.", "connections"))

    control_policy = _control_policy(flow, agents, success_cycle)
    loop_policy = {
        "mode": "pm-checklist" if control_policy["mode"] == "pm-checklist" else "bounded-rework" if rework_loops else "none",
        "maxIterations": _loop_max_iterations(flow) if rework_loops else 0,
        "loops": rework_loops,
    }

    return {
        "valid": not errors,
        "status": "valid" if not errors else "invalid",
        "errors": errors,
        "warnings": warnings,
        "issues": errors,
        "startNodeCandidates": start_node_candidates,
        "selectedStartAgentId": selected or (start_node_candidates[0]["agentId"] if len(start_node_candidates) == 1 else ""),
        "loopPolicy": loop_policy,
        "controlPolicy": control_policy,
        "checkedAt": flow["updatedAt"],
    }


def _issue(code: str, message: str, path: str) -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


def _loop_max_iterations(flow: dict[str, Any]) -> int:
    settings = flow.get("presetSettings") if isinstance(flow.get("presetSettings"), dict) else {}
    return _positive_int(flow.get("maxLoopIterations") or settings.get("maxLoopIterations"), DEFAULT_MAX_LOOP_ITERATIONS)


def _control_policy(flow: dict[str, Any], agents: list[dict[str, Any]], success_cycle: list[str]) -> dict[str, Any]:
    pm_agents = [agent for agent in agents if str(agent.get("role") or "").strip() == "PM"]
    if not pm_agents:
        return {"mode": "none"}
    settings = flow.get("presetSettings") if isinstance(flow.get("presetSettings"), dict) else {}
    return {
        "mode": "pm-checklist",
        "pmAgentId": str(pm_agents[0].get("id") or ""),
        "checklistSource": "planner-output",
        "maxAttemptsPerItem": _positive_int(
            flow.get("maxChecklistAttempts") or settings.get("maxChecklistAttempts"),
            DEFAULT_MAX_CHECKLIST_ATTEMPTS,
        ),
        "successCycleAllowed": bool(success_cycle),
    }


def _cycle_has_role(cycle: list[str], agents: list[dict[str, Any]], role: str) -> bool:
    roles_by_id = {str(agent.get("id") or ""): str(agent.get("role") or "").strip() for agent in agents}
    return any(roles_by_id.get(agent_id) == role for agent_id in cycle)


def _agent_name(agents: list[dict[str, Any]], agent_id: str) -> str:
    for agent in agents:
        if agent.get("id") == agent_id:
            return str(agent.get("name") or agent_id)
    return agent_id


def _find_cycle(graph: dict[str, list[str]]) -> list[str]:
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(node: str) -> list[str]:
        if node in visiting:
            start = stack.index(node) if node in stack else 0
            return [*stack[start:], node]
        if node in visited:
            return []
        visiting.add(node)
        stack.append(node)
        for child in graph.get(node, []):
            cycle = visit(child)
            if cycle:
                return cycle
        stack.pop()
        visiting.remove(node)
        visited.add(node)
        return []

    for node in graph:
        cycle = visit(node)
        if cycle:
            return cycle
    return []


def _summary(flow: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": flow["id"],
        "name": flow["name"],
        "version": flow["version"],
        "agentCount": len(flow.get("agents") or []),
        "connectionCount": len(flow.get("connections") or []),
        "validationStatus": flow.get("validationStatus") or "unknown",
        "createdAt": flow.get("createdAt"),
        "updatedAt": flow.get("updatedAt"),
    }


def _compile_profile_snapshot(
    flow: dict[str, Any],
    agent: dict[str, Any],
    *,
    compiled_at: str,
    approval_id: str,
) -> dict[str, Any]:
    work_package = {
        field: str((agent.get("workPackage") or {}).get(field) or "")
        for field in sorted(WORK_PACKAGE_FIELDS)
    }
    snapshot_id = f"profile-{flow['id']}-v{flow['version']}-{_slug(str(agent.get('id') or 'agent'))}-{uuid.uuid4().hex[:8]}"
    role = str(agent.get("role") or "Agent")
    display_name = str(agent.get("name") or role)
    developer_instructions = "\n".join(
        [
            f"Role: {role}",
            f"Instructions: {work_package['instructions']}",
            f"Constraints: {work_package['constraints']}",
            f"Allowed tools/actions: {work_package['allowedTools']}",
            f"Expected output: {work_package['expectedOutput']}",
        ]
    )
    initial_user_message = "\n".join(
        [
            f"Current objective: {work_package['currentObjective']}",
            f"Inputs/artifacts: {work_package['inputsArtifacts']}",
            f"Previous outputs: {work_package['previousOutputs']}",
            f"Expected output: {work_package['expectedOutput']}",
        ]
    )
    access_mode = str(agent.get("accessMode") or "workspace-write")
    return {
        "schemaVersion": 1,
        "snapshotId": snapshot_id,
        "source": {
            "flowId": flow["id"],
            "flowVersion": flow["version"],
            "sourceCardId": str(agent.get("id") or ""),
            "compiledAt": compiled_at,
            "approvalId": approval_id,
        },
        "displayName": display_name,
        "role": role,
        "model": {
            "name": str(agent.get("llm") or ""),
            "reasoning": str(agent.get("reasoning") or "medium"),
            "speed": str(agent.get("speed") or "balanced"),
        },
        "workPackage": work_package,
        "runtimePolicy": {
            "sandboxMode": access_mode,
            "approvalPolicy": "never",
            "networkAccess": True,
            "workspaceRootPolicy": "project-root",
            "maxTurns": 12,
        },
        "codexAppServer": {
            "workerName": _slug(display_name),
            "developerInstructions": developer_instructions,
            "initialUserMessage": initial_user_message,
        },
    }


def _compile_graph(flow: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    nodes = [
        {
            "agentId": str(agent.get("id") or ""),
            "name": str(agent.get("name") or ""),
            "role": str(agent.get("role") or ""),
        }
        for agent in flow.get("agents", [])
    ]
    edges = [
        {
            "id": str(connection.get("id") or ""),
            "fromAgentId": str(connection.get("fromAgentId") or ""),
            "toAgentId": str(connection.get("toAgentId") or ""),
            "fromPort": str(connection.get("fromPort") or "success"),
            "toPort": "input",
        }
        for connection in flow.get("connections", [])
    ]
    return {
        "startAgentId": validation.get("selectedStartAgentId") or "",
        "nodes": nodes,
        "edges": edges,
        "executionOrder": _execution_order(nodes, edges, str(validation.get("selectedStartAgentId") or "")),
        "loopPolicy": validation.get("loopPolicy") or {"mode": "none", "maxIterations": 0, "loops": []},
        "controlPolicy": validation.get("controlPolicy") or {"mode": "none"},
    }


def _compile_run_context(value: Any) -> dict[str, str]:
    context = value if isinstance(value, dict) else {}
    return {
        "taskSummary": str(context.get("taskSummary") or "").strip()[:4000],
        "firstPromptSummary": str(context.get("firstPromptSummary") or "").strip()[:4000],
    }


def _execution_order(nodes: list[dict[str, str]], edges: list[dict[str, str]], start_agent_id: str) -> list[str]:
    if start_agent_id:
        return _success_reachable_order(nodes, edges, start_agent_id)
    return _topological_order(nodes, edges)


def _success_reachable_order(nodes: list[dict[str, str]], edges: list[dict[str, str]], start_agent_id: str) -> list[str]:
    node_ids = [node["agentId"] for node in nodes]
    node_set = set(node_ids)
    outgoing = {node_id: [] for node_id in node_ids}
    for edge in edges:
        if edge.get("fromPort") != "success":
            continue
        source = edge["fromAgentId"]
        target = edge["toAgentId"]
        if source in outgoing and target in node_set:
            outgoing[source].append(target)
    order: list[str] = []
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visited or node_id not in node_set:
            return
        visited.add(node_id)
        order.append(node_id)
        for target in outgoing.get(node_id, []):
            visit(target)

    visit(start_agent_id)
    for node_id in _topological_order(nodes, edges):
        if node_id not in visited:
            order.append(node_id)
            visited.add(node_id)
    return order


def _topological_order(nodes: list[dict[str, str]], edges: list[dict[str, str]]) -> list[str]:
    node_ids = [node["agentId"] for node in nodes]
    incoming = {node_id: 0 for node_id in node_ids}
    outgoing = {node_id: [] for node_id in node_ids}
    for edge in edges:
        if edge.get("fromPort") == "failure":
            continue
        source = edge["fromAgentId"]
        target = edge["toAgentId"]
        if source in outgoing and target in incoming:
            outgoing[source].append(target)
            incoming[target] += 1
    ready = [node_id for node_id in node_ids if incoming[node_id] == 0]
    order: list[str] = []
    while ready:
        node_id = ready.pop(0)
        order.append(node_id)
        for target in outgoing[node_id]:
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)
    for node_id in node_ids:
        if node_id not in order:
            order.append(node_id)
    return order


def _write_flow(root: Path, flow: dict[str, Any]) -> None:
    runtime_store.upsert_json_document(root, "agent_flows", flow["id"], flow)


def _read_flow_path(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AgentFlowError("Agent flow was not found.")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AgentFlowError("Saved agent flow is not an object.")
    return data


def _flow_dir(root: Path) -> Path:
    return root / FLOW_DIR


def _flow_path(root: Path, flow_id: str) -> Path:
    return _flow_dir(root) / f"{_validate_flow_id(flow_id)}.json"


def _manifest_path(root: Path, manifest_id: str) -> Path:
    return root / MANIFEST_DIR / f"{_validate_flow_id(manifest_id)}.json"


def _unique_flow_id(root: Path, name: str) -> str:
    base = _slug(name)
    candidate = base
    index = 2
    while runtime_store.json_document_exists(root, "agent_flows", candidate) or _flow_path(root, candidate).exists():
        candidate = f"{base}-{index}"
        index += 1
    return candidate


def _validate_flow_id(flow_id: str) -> str:
    value = str(flow_id or "").strip().lower()
    if not FLOW_ID_PATTERN.match(value):
        raise AgentFlowError("Flow id must be a lowercase slug.")
    return value


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return (slug or "agent-flow")[:70].strip("-") or "agent-flow"


def _limited_text(value: Any, fallback: str, limit: int) -> str:
    text = str(value or "").strip()
    return (text or fallback)[:limit]


def _positive_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def _number(value: Any, fallback: int) -> int:
    try:
        return round(float(value))
    except (TypeError, ValueError):
        return fallback


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
