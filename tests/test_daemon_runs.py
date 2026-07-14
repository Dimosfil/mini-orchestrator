from __future__ import annotations

import pytest

from mini_orchestrator.agent_flows import compile_saved_agent_flow, create_agent_flow
from mini_orchestrator import runtime_store
from mini_orchestrator.ui import build_live_runs_payload
from mini_orchestrator.daemon_runs import (
    build_demo_daemon_runs,
    build_local_daemon_runs,
    resume_manifest_run,
    run_manifest_dry_run,
    run_single_card_dry_run,
    set_run_review_decision,
)


def sample_one_card_flow() -> dict:
    work_package = {
        "instructions": "Act as Executor.",
        "currentObjective": "Complete a dry-run task.",
        "inputsArtifacts": "Compiled manifest.",
        "constraints": "Do not launch real workers.",
        "previousOutputs": "None.",
        "allowedTools": "Dry-run transport.",
        "expectedOutput": "Dry-run result.",
    }
    return {
        "name": "One Card Flow",
        "agents": [
            {
                "id": "executor",
                "name": "Executor",
                "role": "Executor",
                "preset": "executor",
                "llm": "gpt-5.4",
                "speed": "balanced",
                "reasoning": "medium",
                "accessMode": "workspace-write",
                "workPackage": work_package,
                "x": 10,
                "y": 20,
            }
        ],
        "connections": [],
        "nextAgentNumber": 2,
    }


def sample_three_card_flow() -> dict:
    def agent(agent_id: str, role: str) -> dict:
        item = sample_one_card_flow()["agents"][0].copy()
        item["id"] = agent_id
        item["name"] = role
        item["role"] = role
        item["preset"] = role.lower()
        item["workPackage"] = item["workPackage"].copy()
        item["workPackage"]["instructions"] = f"Act as {role}."
        item["workPackage"]["currentObjective"] = f"Complete {role} step."
        return item

    return {
        "name": "Three Card Flow",
        "agents": [agent("planner", "Planner"), agent("executor", "Executor"), agent("reviewer", "Reviewer")],
        "connections": [
            {"id": "planner-executor", "fromAgentId": "planner", "toAgentId": "executor", "fromPort": "success"},
            {"id": "executor-reviewer", "fromAgentId": "executor", "toAgentId": "reviewer", "fromPort": "success"},
        ],
        "nextAgentNumber": 4,
    }


def sample_qa_rework_flow() -> dict:
    flow = sample_three_card_flow()
    qa = flow["agents"][1].copy()
    qa["id"] = "qa"
    qa["name"] = "QA"
    qa["role"] = "QA"
    qa["preset"] = "qa"
    qa["workPackage"] = qa["workPackage"].copy()
    qa["workPackage"]["instructions"] = "Act as QA."
    flow["name"] = "QA Rework Flow"
    flow["agents"].insert(2, qa)
    flow["connections"] = [
        {"id": "planner-executor", "fromAgentId": "planner", "toAgentId": "executor", "fromPort": "success"},
        {"id": "executor-qa", "fromAgentId": "executor", "toAgentId": "qa", "fromPort": "success"},
        {"id": "qa-executor", "fromAgentId": "qa", "toAgentId": "executor", "fromPort": "failure"},
        {"id": "qa-reviewer", "fromAgentId": "qa", "toAgentId": "reviewer", "fromPort": "success"},
    ]
    return flow
def test_demo_daemon_runs_are_schema_shaped():
    payload = build_demo_daemon_runs()

    assert payload["source"] == "demo"
    assert payload["summary"]["total"] == len(payload["runs"])
    assert payload["summary"]["active"] == 2

    run = payload["runs"][0]
    assert run["schemaVersion"] == 1
    assert run["runId"]
    assert run["task"]["project"] == "mini-orchestrator"
    assert run["profileSnapshotId"] in payload["profiles"]
    assert run["status"] in {"queued", "claimed", "running", "blocked", "retrying", "review", "done", "failed"}
    assert run["tokens"]["total"] == run["tokens"]["input"] + run["tokens"]["output"]
    assert run["artifacts"]["eventLogPath"].endswith(".jsonl")
    assert run["schemaVersion"] == 1
    assert run["sourceLabel"] == "Dispatcher"
    assert isinstance(run["stages"], list)
    assert run["stale"]["isStale"] is False


def test_single_card_daemon_dry_run_writes_state_and_replayable_events(tmp_path):
    flow = create_agent_flow({"flow": sample_one_card_flow()}, tmp_path)
    manifest = compile_saved_agent_flow(flow["id"], tmp_path, {"approval": {"approved": True}})
    snapshot_id = manifest["profileSnapshots"][0]["snapshotId"]

    state = run_single_card_dry_run(
        manifest,
        snapshot_id,
        tmp_path,
        task={"taskId": "task-1", "sprintId": "sprint-1"},
    )

    assert state["status"] == "review"
    assert state["task"]["taskId"] == "task-1"
    assert state["profileSnapshotId"] == snapshot_id
    assert state["thread"]["turnCount"] == 1
    assert state["artifacts"]["eventLogPath"].startswith("runtime-db://daemon-runs/")
    assert state["currentAgent"] == snapshot_id
    assert state["outputs"][snapshot_id].startswith("Dry-run completed")
    assert state["stages"][0]["status"] == "done"

    event_types = [event.get("type") for event in runtime_store.list_daemon_events(tmp_path, state["runId"])]
    assert "dry_run_started" in event_types
    assert "ready_for_human_review" in event_types

    payload = build_local_daemon_runs(tmp_path)
    assert payload["source"] == "mini-daemon-jsonl"
    assert payload["summary"]["review"] == 1
    assert payload["summary"]["done"] == 0
    assert payload["runs"][0]["runId"] == state["runId"]

    live_payload = build_live_runs_payload(tmp_path)
    assert live_payload["sourceMode"] == "combined"
    assert live_payload["runs"][0]["runId"] == state["runId"]
    assert live_payload["runs"][0]["sourceLabel"] == "Dispatcher"


def test_three_agent_daemon_dry_run_passes_artifacts_and_finishes_done(tmp_path):
    flow = create_agent_flow({"flow": sample_three_card_flow()}, tmp_path)
    manifest = compile_saved_agent_flow(flow["id"], tmp_path, {"approval": {"approved": True}})

    state = run_manifest_dry_run(manifest, tmp_path, reviewer_verdict="done")

    assert state["status"] == "review"
    assert [node["agentId"] for node in state["nodeStates"]] == ["planner", "executor", "reviewer"]
    assert [artifact["agentId"] for artifact in state["flowArtifacts"]] == ["planner", "executor", "reviewer"]
    assert state["flowArtifacts"][2]["verdict"] == "done"
    assert state["thread"]["turnCount"] == 3

    event_types = [event.get("type") for event in runtime_store.list_daemon_events(tmp_path, state["runId"])]
    assert "node_started" in event_types
    assert "ready_for_human_review" in event_types

    accepted = set_run_review_decision(state["runId"], "done", tmp_path)
    assert accepted["status"] == "done"
    assert accepted["review"]["decision"] == "done"
    assert accepted["lastEvent"] == "user accepted result"


def test_daemon_review_rework_keeps_run_in_human_review(tmp_path):
    flow = create_agent_flow({"flow": sample_three_card_flow()}, tmp_path)
    manifest = compile_saved_agent_flow(flow["id"], tmp_path, {"approval": {"approved": True}})
    state = run_manifest_dry_run(manifest, tmp_path, reviewer_verdict="done")

    rework = set_run_review_decision(state["runId"], "rework", tmp_path)

    assert rework["status"] == "review"
    assert rework["review"]["decision"] == "rework"
    assert rework["lastEvent"] == "user requested rework"


def test_three_agent_daemon_dry_run_maps_blocked_verdict(tmp_path):
    flow = create_agent_flow({"flow": sample_three_card_flow()}, tmp_path)
    manifest = compile_saved_agent_flow(flow["id"], tmp_path, {"approval": {"approved": True}})

    state = run_manifest_dry_run(manifest, tmp_path, reviewer_verdict="blocked")

    assert state["status"] == "blocked"
    assert state["reviewerVerdict"] == "blocked"
    assert state["lastError"] == "Reviewer blocked the run."
    assert state["nodeStates"][-1]["agentId"] == "reviewer"
    assert state["nodeStates"][-1]["status"] == "blocked"


def test_reviewer_needs_changes_without_rework_edge_waits_for_human_review(tmp_path):
    flow = create_agent_flow({"flow": sample_three_card_flow()}, tmp_path)
    manifest = compile_saved_agent_flow(flow["id"], tmp_path, {"approval": {"approved": True}})

    state = run_manifest_dry_run(manifest, tmp_path, reviewer_verdict="needs_changes")

    assert state["status"] == "review"
    assert state["reviewerVerdict"] == "needs_changes"
    assert state["workflow"]["nextAgentId"] == ""


def test_manifest_runtime_routes_failure_through_bounded_rework_loop(tmp_path):
    flow = create_agent_flow({"flow": sample_qa_rework_flow()}, tmp_path)
    manifest = compile_saved_agent_flow(flow["id"], tmp_path, {"approval": {"approved": True}})

    state = run_manifest_dry_run(
        manifest,
        tmp_path,
        reviewer_verdict="done",
        node_results={
            "qa": [
                {"status": "failure", "summary": "Defect found", "issues": [{"code": "missing-test"}]},
                {"status": "success", "summary": "QA passed"},
            ]
        },
    )

    assert state["status"] == "review"
    assert [node["agentId"] for node in state["nodeStates"]] == [
        "planner",
        "executor",
        "qa",
        "executor",
        "qa",
        "reviewer",
    ]
    assert state["nodeStates"][2]["status"] == "failed"
    assert state["nodeStates"][4]["status"] == "done"
    assert state["workflow"]["edgeTraversals"]["qa-executor"] == 1
    assert state["flowArtifacts"][2]["issues"] == [{"code": "missing-test"}]

    event_types = [event.get("type") for event in runtime_store.list_daemon_events(tmp_path, state["runId"])]
    assert event_types.count("node_routed") == 5


def test_manifest_runtime_blocks_when_rework_loop_exceeds_limit(tmp_path):
    flow = create_agent_flow({"flow": sample_qa_rework_flow()}, tmp_path)
    manifest = compile_saved_agent_flow(flow["id"], tmp_path, {"approval": {"approved": True}})

    state = run_manifest_dry_run(
        manifest,
        tmp_path,
        node_results={"qa": {"status": "failure", "summary": "Still broken"}},
    )

    assert state["status"] == "blocked"
    assert "maxIterations=3" in state["lastError"]
    assert state["workflow"]["edgeTraversals"]["qa-executor"] == 4


def test_manifest_runtime_resumes_from_sqlite_checkpoint_after_interruption(tmp_path):
    flow = create_agent_flow({"flow": sample_three_card_flow()}, tmp_path)
    manifest = compile_saved_agent_flow(flow["id"], tmp_path, {"approval": {"approved": True}})

    def interrupt_executor(profile, context):
        node_id = profile["source"]["sourceCardId"]
        if node_id == "executor":
            raise RuntimeError("simulated worker exit")
        return {"status": "success", "summary": f"{node_id} completed"}

    with pytest.raises(RuntimeError, match="simulated worker exit"):
        run_manifest_dry_run(manifest, tmp_path, stage_executor=interrupt_executor)

    interrupted = runtime_store.list_json_documents(tmp_path, "daemon_runs")[0]
    assert interrupted["status"] == "interrupted"
    assert interrupted["workflow"]["nextAgentId"] == "executor"
    assert interrupted["workflow"]["nodeAttempts"]["executor"] == 1

    def resume_executor(profile, context):
        node_id = profile["source"]["sourceCardId"]
        verdict = "done" if node_id == "reviewer" else ""
        return {
            "status": "success",
            "summary": f"{node_id} completed",
            "verdict": verdict,
            "metrics": {"inputTokens": 10, "outputTokens": 5, "durationMs": 20},
        }

    resumed = resume_manifest_run(
        interrupted["runId"],
        manifest,
        tmp_path,
        stage_executor=resume_executor,
    )

    assert resumed["status"] == "review"
    assert resumed["workflow"]["nodeAttempts"]["executor"] == 2
    assert [node["status"] for node in resumed["nodeStates"] if node["agentId"] == "executor"] == [
        "interrupted",
        "done",
    ]
    assert resumed["tokens"] == {"input": 20, "output": 10, "total": 30}
