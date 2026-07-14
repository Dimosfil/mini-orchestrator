from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


TERMINAL_STATUSES = {"blocked", "failed", "review"}
STAGE_STATUSES = {"success", "failure", "blocked"}


class WorkflowRuntimeError(ValueError):
    pass


@dataclass(frozen=True)
class StageResult:
    status: str
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    issues: list[dict[str, Any]] = field(default_factory=list)
    verdict: str = ""
    next_agent_id: str = ""
    metrics: dict[str, int | float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["nextAgentId"] = value.pop("next_agent_id")
        return value


StageExecutor = Callable[[dict[str, Any], dict[str, Any]], StageResult | dict[str, Any]]
Checkpoint = Callable[[dict[str, Any], dict[str, Any]], None]


def execute_manifest_graph(
    manifest: dict[str, Any],
    state: dict[str, Any],
    executor: StageExecutor,
    *,
    checkpoint: Checkpoint | None = None,
    task: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute or resume a compiled workflow manifest.

    The caller owns persistence. ``checkpoint`` receives the mutable state and
    the event after every meaningful transition, so SQLite-backed callers can
    resume from ``workflow.nextAgentId`` after a process interruption.
    """

    graph, profiles = _validated_manifest(manifest)
    workflow = _initialize_workflow_state(manifest, state, graph)
    runtime_policy = _runtime_policy(manifest, len(profiles))
    profile_by_agent = {
        str(profile.get("source", {}).get("sourceCardId") or ""): profile
        for profile in profiles
    }
    edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []

    while workflow.get("nextAgentId"):
        node_id = str(workflow["nextAgentId"])
        if node_id not in profile_by_agent:
            return _stop(
                state,
                "failed",
                f"Workflow profile is missing for node: {node_id}",
                checkpoint,
            )
        if int(workflow.get("stepCount") or 0) >= runtime_policy["maxWorkflowSteps"]:
            return _stop(
                state,
                "blocked",
                f"Workflow exceeded maxWorkflowSteps={runtime_policy['maxWorkflowSteps']}.",
                checkpoint,
            )
        if _elapsed_seconds(state.get("createdAt")) > runtime_policy["maxRuntimeSeconds"]:
            return _stop(
                state,
                "blocked",
                f"Workflow exceeded maxRuntimeSeconds={runtime_policy['maxRuntimeSeconds']}.",
                checkpoint,
            )

        attempts = workflow.setdefault("nodeAttempts", {})
        attempt = int(attempts.get(node_id) or 0) + 1
        attempts[node_id] = attempt
        workflow["stepCount"] = int(workflow.get("stepCount") or 0) + 1
        workflow["currentAgentId"] = node_id
        state["currentAgent"] = node_id
        state["status"] = "running"
        state["lastError"] = None
        started_at = _utc_now()
        node_state = {
            "agentId": node_id,
            "snapshotId": str(profile_by_agent[node_id].get("snapshotId") or node_id),
            "role": str(profile_by_agent[node_id].get("role") or "Agent"),
            "attempt": attempt,
            "status": "running",
            "startedAt": started_at,
            "completedAt": None,
        }
        state.setdefault("nodeStates", []).append(node_state)
        _emit(
            state,
            checkpoint,
            {
                "time": started_at,
                "type": "node_started",
                "runId": state.get("runId"),
                "agentId": node_id,
                "snapshotId": node_state["snapshotId"],
                "attempt": attempt,
                "inputArtifacts": _context_artifacts(state, runtime_policy["maxContextArtifacts"]),
            },
        )

        context = {
            "task": deepcopy(task or state.get("task") or {}),
            "attempt": attempt,
            "step": workflow["stepCount"],
            "inputArtifacts": _context_artifacts(state, runtime_policy["maxContextArtifacts"]),
            "runtimePolicy": deepcopy(runtime_policy),
        }
        try:
            result = normalize_stage_result(executor(deepcopy(profile_by_agent[node_id]), context))
        except Exception as exc:
            state["status"] = "interrupted"
            state["lastError"] = f"{type(exc).__name__}: {exc}"
            node_state["status"] = "interrupted"
            state["updatedAt"] = _utc_now()
            _emit(
                state,
                checkpoint,
                {
                    "time": state["updatedAt"],
                    "type": "node_interrupted",
                    "runId": state.get("runId"),
                    "agentId": node_id,
                    "attempt": attempt,
                    "error": state["lastError"],
                },
            )
            raise

        completed_at = _utc_now()
        artifact = _stage_artifact(node_id, node_state["role"], attempt, result)
        state.setdefault("flowArtifacts", []).append(artifact)
        node_state["status"] = {
            "success": "done",
            "failure": "failed",
            "blocked": "blocked",
        }[result.status]
        node_state["completedAt"] = completed_at
        node_state["result"] = result.to_dict()
        state["updatedAt"] = completed_at
        state["lastEvent"] = f"{node_id}: {result.status}"
        _accumulate_metrics(state, result.metrics)
        _emit(
            state,
            checkpoint,
            {
                "time": completed_at,
                "type": "node_completed",
                "runId": state.get("runId"),
                "agentId": node_id,
                "snapshotId": node_state["snapshotId"],
                "attempt": attempt,
                "outcome": result.status,
                "artifact": artifact,
            },
        )

        if result.status == "blocked":
            return _stop(state, "blocked", result.summary, checkpoint, verdict=result.verdict)

        try:
            route = _select_route(node_id, result, edges)
        except WorkflowRuntimeError as exc:
            return _stop(state, "blocked", str(exc), checkpoint, verdict=result.verdict)
        if route is None and result.status == "failure":
            if result.verdict == "needs_changes":
                return _stop(state, "review", result.summary, checkpoint, verdict=result.verdict)
            max_attempts = runtime_policy["maxRetriesPerNode"] + 1
            if attempt < max_attempts:
                workflow["nextAgentId"] = node_id
                state["status"] = "retrying"
                _emit(
                    state,
                    checkpoint,
                    {
                        "time": _utc_now(),
                        "type": "node_retry_scheduled",
                        "runId": state.get("runId"),
                        "agentId": node_id,
                        "attempt": attempt,
                        "maxAttempts": max_attempts,
                    },
                )
                continue
            return _stop(state, "failed", result.summary, checkpoint, verdict=result.verdict)

        if route is None:
            return _finish_success(state, result, checkpoint)

        edge_key = str(route.get("id") or f"{node_id}:{result.status}:{route.get('toAgentId')}")
        traversals = workflow.setdefault("edgeTraversals", {})
        traversals[edge_key] = int(traversals.get(edge_key) or 0) + 1
        edge_limit = _edge_iteration_limit(graph, route)
        if edge_limit and traversals[edge_key] > edge_limit:
            return _stop(
                state,
                "blocked",
                f"Workflow edge {edge_key} exceeded maxIterations={edge_limit}.",
                checkpoint,
            )
        next_agent_id = str(route.get("toAgentId") or "")
        workflow["nextAgentId"] = next_agent_id
        state["status"] = "queued"
        _emit(
            state,
            checkpoint,
            {
                "time": _utc_now(),
                "type": "node_routed",
                "runId": state.get("runId"),
                "fromAgentId": node_id,
                "toAgentId": next_agent_id,
                "outcome": result.status,
                "edgeId": edge_key,
                "iteration": traversals[edge_key],
            },
        )

    return _stop(state, "failed", "Workflow has no next node and no terminal result.", checkpoint)


def normalize_stage_result(value: StageResult | dict[str, Any]) -> StageResult:
    if isinstance(value, StageResult):
        result = value
    elif isinstance(value, dict):
        status = str(value.get("status") or "success").strip().casefold().replace("-", "_")
        if status in {"done", "ok", "passed"}:
            status = "success"
        if status in {"error", "failed", "needs_changes", "retrying"}:
            status = "failure"
        result = StageResult(
            status=status,
            summary=str(value.get("summary") or "").strip(),
            data=deepcopy(value.get("data")) if isinstance(value.get("data"), dict) else {},
            artifacts=deepcopy(value.get("artifacts")) if isinstance(value.get("artifacts"), list) else [],
            issues=deepcopy(value.get("issues")) if isinstance(value.get("issues"), list) else [],
            verdict=_normalize_verdict(value.get("verdict")),
            next_agent_id=str(value.get("nextAgentId") or value.get("next_agent_id") or "").strip(),
            metrics=_normalize_metrics(value.get("metrics")),
        )
    else:
        raise WorkflowRuntimeError("Stage executor must return StageResult or an object.")
    if result.status not in STAGE_STATUSES:
        raise WorkflowRuntimeError(f"Unsupported stage status: {result.status}")
    if not result.summary:
        raise WorkflowRuntimeError("Stage result summary is required.")
    return result


def _validated_manifest(manifest: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    graph = manifest.get("graph") if isinstance(manifest.get("graph"), dict) else {}
    profiles = manifest.get("profileSnapshots") if isinstance(manifest.get("profileSnapshots"), list) else []
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    if not profiles:
        raise WorkflowRuntimeError("Run manifest has no profile snapshots.")
    if not nodes:
        raise WorkflowRuntimeError("Run manifest graph has no nodes.")
    node_ids = {str(node.get("agentId") or "") for node in nodes if isinstance(node, dict)}
    profile_ids = {
        str(profile.get("source", {}).get("sourceCardId") or "")
        for profile in profiles
        if isinstance(profile, dict)
    }
    if node_ids != profile_ids:
        raise WorkflowRuntimeError("Run manifest graph does not cover every profile snapshot.")
    start = str(graph.get("startAgentId") or "")
    if start not in node_ids:
        raise WorkflowRuntimeError("Run manifest graph has no valid start node.")
    return graph, profiles


def _initialize_workflow_state(
    manifest: dict[str, Any], state: dict[str, Any], graph: dict[str, Any]
) -> dict[str, Any]:
    existing = state.get("workflow")
    if isinstance(existing, dict) and existing.get("nextAgentId"):
        state.setdefault("nodeStates", [])
        state.setdefault("flowArtifacts", [])
        return existing
    workflow = {
        "schemaVersion": 1,
        "manifestId": str(manifest.get("manifestId") or ""),
        "startAgentId": str(graph.get("startAgentId") or ""),
        "currentAgentId": "",
        "nextAgentId": str(graph.get("startAgentId") or ""),
        "stepCount": 0,
        "nodeAttempts": {},
        "edgeTraversals": {},
    }
    state["workflow"] = workflow
    state.setdefault("nodeStates", [])
    state.setdefault("flowArtifacts", [])
    return workflow


def _runtime_policy(manifest: dict[str, Any], node_count: int) -> dict[str, int]:
    value = manifest.get("runtimePolicy") if isinstance(manifest.get("runtimePolicy"), dict) else {}
    return {
        "maxWorkflowSteps": _positive_int(value.get("maxWorkflowSteps"), max(20, node_count * 4)),
        "maxRetriesPerNode": _non_negative_int(value.get("maxRetriesPerNode"), 1),
        "maxContextArtifacts": _positive_int(value.get("maxContextArtifacts"), 8),
        "maxRuntimeSeconds": _positive_int(value.get("maxRuntimeSeconds"), 1800),
    }


def _select_route(
    node_id: str, result: StageResult, edges: list[dict[str, Any]]
) -> dict[str, Any] | None:
    port = "success" if result.status == "success" else "failure"
    candidates = [
        edge
        for edge in edges
        if isinstance(edge, dict)
        and str(edge.get("fromAgentId") or "") == node_id
        and str(edge.get("fromPort") or "success") == port
    ]
    if result.next_agent_id:
        selected = [edge for edge in candidates if str(edge.get("toAgentId") or "") == result.next_agent_id]
        if len(selected) != 1:
            raise WorkflowRuntimeError(
                f"Stage selected unavailable or ambiguous route {node_id} -> {result.next_agent_id} ({port})."
            )
        return selected[0]
    if len(candidates) > 1:
        targets = ", ".join(str(edge.get("toAgentId") or "") for edge in candidates)
        raise WorkflowRuntimeError(
            f"Node {node_id} has multiple {port} routes ({targets}); stage result must set nextAgentId."
        )
    return candidates[0] if candidates else None


def _edge_iteration_limit(graph: dict[str, Any], edge: dict[str, Any]) -> int:
    policy = graph.get("loopPolicy") if isinstance(graph.get("loopPolicy"), dict) else {}
    loops = policy.get("loops") if isinstance(policy.get("loops"), list) else []
    for loop in loops:
        if not isinstance(loop, dict):
            continue
        if (
            str(loop.get("fromAgentId") or "") == str(edge.get("fromAgentId") or "")
            and str(loop.get("toAgentId") or "") == str(edge.get("toAgentId") or "")
            and str(loop.get("fromPort") or "failure") == str(edge.get("fromPort") or "success")
        ):
            return _positive_int(loop.get("maxIterations"), 1)
    return 0


def _stage_artifact(node_id: str, role: str, attempt: int, result: StageResult) -> dict[str, Any]:
    artifact = {
        "schemaVersion": 1,
        "artifactId": f"artifact-{node_id}-{attempt}",
        "agentId": node_id,
        "role": role,
        "attempt": attempt,
        "status": result.status,
        "summary": result.summary,
        "data": deepcopy(result.data),
        "artifacts": deepcopy(result.artifacts),
        "issues": deepcopy(result.issues),
    }
    if result.verdict:
        artifact["verdict"] = result.verdict
    return artifact


def _context_artifacts(state: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    artifacts = state.get("flowArtifacts") if isinstance(state.get("flowArtifacts"), list) else []
    return deepcopy(artifacts[-limit:])


def _finish_success(
    state: dict[str, Any], result: StageResult, checkpoint: Checkpoint | None
) -> dict[str, Any]:
    verdict = result.verdict or "done"
    if verdict == "blocked":
        return _stop(state, "blocked", result.summary, checkpoint, verdict=verdict)
    if verdict == "failed":
        return _stop(state, "failed", result.summary, checkpoint, verdict=verdict)
    if verdict == "needs_changes":
        return _stop(state, "review", result.summary, checkpoint, verdict=verdict)
    return _stop(state, "review", "ready_for_human_review", checkpoint, verdict=verdict)


def _stop(
    state: dict[str, Any],
    status: str,
    message: str,
    checkpoint: Checkpoint | None,
    *,
    verdict: str = "",
) -> dict[str, Any]:
    now = _utc_now()
    state["status"] = status
    state["updatedAt"] = now
    state["lastEvent"] = "ready_for_human_review" if status == "review" else message
    state["lastError"] = message if status in {"blocked", "failed"} else None
    if verdict:
        state["reviewerVerdict"] = verdict
    workflow = state.get("workflow") if isinstance(state.get("workflow"), dict) else {}
    workflow["nextAgentId"] = ""
    event_type = "ready_for_human_review" if status == "review" else "run_completed"
    _emit(
        state,
        checkpoint,
        {
            "time": now,
            "type": event_type,
            "runId": state.get("runId"),
            "status": status,
            "reviewerVerdict": state.get("reviewerVerdict"),
            "message": message,
        },
    )
    return state


def _emit(state: dict[str, Any], checkpoint: Checkpoint | None, event: dict[str, Any]) -> None:
    state["updatedAt"] = str(event.get("time") or _utc_now())
    stale = state.get("stale")
    if isinstance(stale, dict):
        stale["lastEventAt"] = state["updatedAt"]
    if checkpoint:
        checkpoint(state, event)


def _accumulate_metrics(state: dict[str, Any], metrics: dict[str, int | float]) -> None:
    tokens = state.setdefault("tokens", {"input": 0, "output": 0, "total": 0})
    input_tokens = int(metrics.get("inputTokens") or 0)
    output_tokens = int(metrics.get("outputTokens") or 0)
    tokens["input"] = int(tokens.get("input") or 0) + input_tokens
    tokens["output"] = int(tokens.get("output") or 0) + output_tokens
    tokens["total"] = int(tokens["input"]) + int(tokens["output"])
    workflow = state.get("workflow") if isinstance(state.get("workflow"), dict) else {}
    runtime_metrics = workflow.setdefault("metrics", {"durationMs": 0})
    runtime_metrics["durationMs"] = int(runtime_metrics.get("durationMs") or 0) + int(metrics.get("durationMs") or 0)


def _normalize_metrics(value: Any) -> dict[str, int | float]:
    source = value if isinstance(value, dict) else {}
    return {
        "inputTokens": _non_negative_int(source.get("inputTokens"), 0),
        "outputTokens": _non_negative_int(source.get("outputTokens"), 0),
        "durationMs": _non_negative_int(source.get("durationMs"), 0),
    }


def _normalize_verdict(value: Any) -> str:
    verdict = str(value or "").strip().casefold().replace("-", "_")
    return verdict if verdict in {"done", "needs_changes", "blocked", "failed"} else ""


def _elapsed_seconds(value: Any) -> int:
    try:
        created = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return max(0, int((datetime.now(timezone.utc) - created.astimezone(timezone.utc)).total_seconds()))
    except (TypeError, ValueError):
        return 0


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _non_negative_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
