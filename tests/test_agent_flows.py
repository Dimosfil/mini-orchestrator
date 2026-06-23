from __future__ import annotations

import json
import threading
import urllib.request
from typing import Any

from mini_orchestrator import ui
from mini_orchestrator.agent_flows import (
    compile_saved_agent_flow,
    create_agent_flow,
    list_agent_flows,
    read_agent_flow,
    update_agent_flow,
    validate_saved_agent_flow,
)


def sample_agent(agent_id: str, name: str, role: str) -> dict[str, Any]:
    return {
        "id": agent_id,
        "name": name,
        "role": role,
        "preset": role.lower(),
        "llm": "gpt-5.4",
        "speed": "balanced",
        "reasoning": "medium",
        "accessMode": "workspace-write",
        "workPackage": {
            "instructions": f"Act as {role}.",
            "currentObjective": "Complete the assigned workflow step.",
            "inputsArtifacts": "Saved flow and task context.",
            "constraints": "Stay within the approved flow.",
            "previousOutputs": "Use structured prior outputs only.",
            "allowedTools": "Read, write scoped files, and report.",
            "expectedOutput": "Structured result for the next node.",
        },
    }


def sample_flow(name: str = "Planner Flow") -> dict[str, Any]:
    return {
        "name": name,
        "agents": [
            {**sample_agent("planner", "Planner", "Planner"), "x": 10, "y": 20},
            {**sample_agent("executor", "Executor", "Executor"), "x": 320, "y": 20},
            {**sample_agent("reviewer", "Reviewer", "Reviewer"), "x": 630, "y": 20},
        ],
        "connections": [
            {
                "id": "planner-to-executor",
                "fromAgentId": "planner",
                "toAgentId": "executor",
                "fromPort": "success",
            },
            {
                "id": "executor-to-reviewer",
                "fromAgentId": "executor",
                "toAgentId": "reviewer",
                "fromPort": "success",
            },
        ],
        "presetSettings": {"planner": {"speed": "balanced"}},
        "nextAgentNumber": 3,
    }


def sample_one_card_flow(name: str = "One Card Flow") -> dict[str, Any]:
    return {
        "name": name,
        "agents": [{**sample_agent("executor", "Executor", "Executor"), "x": 10, "y": 20}],
        "connections": [],
        "presetSettings": {},
        "nextAgentNumber": 2,
    }


def test_agent_flow_storage_creates_lists_reads_and_updates(tmp_path) -> None:
    created = create_agent_flow({"flow": sample_flow()}, tmp_path)

    assert created["id"] == "planner-flow"
    assert created["version"] == 1
    assert created["validationStatus"] == "valid"
    assert list_agent_flows(tmp_path)[0]["agentCount"] == 3

    loaded = read_agent_flow(created["id"], tmp_path)
    assert loaded["connections"][0]["toPort"] == "input"

    replacement = sample_flow("Planner Flow Updated")
    replacement["connections"].append(
        {"id": "missing", "fromAgentId": "planner", "toAgentId": "missing-reviewer", "fromPort": "failure"}
    )
    updated = update_agent_flow(created["id"], {"flow": replacement}, tmp_path)

    assert updated["version"] == 2
    assert updated["name"] == "Planner Flow Updated"
    assert updated["validationStatus"] == "invalid"
    assert updated["validation"]["issues"][0]["code"] == "missing_to_agent"


def test_agent_flow_validation_accepts_default_chain(tmp_path) -> None:
    created = create_agent_flow({"flow": sample_flow()}, tmp_path)

    validation = validate_saved_agent_flow(created["id"], tmp_path)

    assert validation["valid"] is True
    assert validation["errors"] == []
    assert validation["startNodeCandidates"] == [{"agentId": "planner", "name": "Planner"}]
    assert validation["selectedStartAgentId"] == "planner"


def test_agent_flow_validation_accepts_qa_role(tmp_path) -> None:
    flow = sample_one_card_flow("QA Flow")
    flow["agents"] = [{**sample_agent("qa", "QA", "QA"), "x": 10, "y": 20}]
    created = create_agent_flow({"flow": flow}, tmp_path)

    validation = validate_saved_agent_flow(created["id"], tmp_path)

    assert validation["valid"] is True
    assert validation["errors"] == []
    assert validation["startNodeCandidates"] == [{"agentId": "qa", "name": "QA"}]
    assert validation["selectedStartAgentId"] == "qa"


def test_agent_flow_validation_accepts_bounded_qa_rework_loop(tmp_path) -> None:
    flow = sample_flow("QA Rework Flow")
    flow["agents"].insert(2, {**sample_agent("qa", "QA", "QA"), "x": 500, "y": 20})
    flow["connections"] = [
        {"id": "planner-to-executor", "fromAgentId": "planner", "toAgentId": "executor", "fromPort": "success"},
        {"id": "executor-to-qa", "fromAgentId": "executor", "toAgentId": "qa", "fromPort": "success"},
        {"id": "qa-to-executor", "fromAgentId": "qa", "toAgentId": "executor", "fromPort": "failure"},
        {"id": "qa-to-reviewer", "fromAgentId": "qa", "toAgentId": "reviewer", "fromPort": "success"},
    ]
    created = create_agent_flow({"flow": flow}, tmp_path)

    validation = validate_saved_agent_flow(created["id"], tmp_path)
    manifest = compile_saved_agent_flow(created["id"], tmp_path, {"approval": {"approved": True}})

    assert validation["valid"] is True
    assert validation["errors"] == []
    assert validation["loopPolicy"]["mode"] == "bounded-rework"
    assert validation["loopPolicy"]["loops"] == [
        {"fromAgentId": "qa", "toAgentId": "executor", "fromPort": "failure", "maxIterations": 3}
    ]
    assert manifest["graph"]["executionOrder"] == ["planner", "executor", "qa", "reviewer"]
    assert manifest["graph"]["loopPolicy"]["mode"] == "bounded-rework"


def test_agent_flow_validation_accepts_pm_checklist_control_loop(tmp_path) -> None:
    flow = sample_flow("PM Checklist Flow")
    flow["agents"] = [
        {**sample_agent("planner", "Planner", "Planner"), "x": 10, "y": 20},
        {**sample_agent("pm", "PM", "PM"), "x": 250, "y": 20},
        {**sample_agent("executor", "Executor", "Executor"), "x": 490, "y": 20},
        {**sample_agent("qa", "QA", "QA"), "x": 730, "y": 20},
        {**sample_agent("reviewer", "Reviewer", "Reviewer"), "x": 970, "y": 20},
    ]
    flow["connections"] = [
        {"id": "planner-to-pm", "fromAgentId": "planner", "toAgentId": "pm", "fromPort": "success"},
        {"id": "pm-to-executor", "fromAgentId": "pm", "toAgentId": "executor", "fromPort": "success"},
        {"id": "executor-to-qa", "fromAgentId": "executor", "toAgentId": "qa", "fromPort": "success"},
        {"id": "qa-to-pm", "fromAgentId": "qa", "toAgentId": "pm", "fromPort": "success"},
        {"id": "qa-to-executor", "fromAgentId": "qa", "toAgentId": "executor", "fromPort": "failure"},
        {"id": "pm-to-reviewer", "fromAgentId": "pm", "toAgentId": "reviewer", "fromPort": "success"},
    ]
    created = create_agent_flow({"flow": flow}, tmp_path)

    validation = validate_saved_agent_flow(created["id"], tmp_path)
    manifest = compile_saved_agent_flow(created["id"], tmp_path, {"approval": {"approved": True}})

    assert validation["valid"] is True
    assert validation["errors"] == []
    assert validation["selectedStartAgentId"] == "planner"
    assert validation["controlPolicy"] == {
        "mode": "pm-checklist",
        "pmAgentId": "pm",
        "checklistSource": "planner-output",
        "maxAttemptsPerItem": 3,
        "successCycleAllowed": True,
    }
    assert manifest["graph"]["executionOrder"] == ["planner", "pm", "executor", "qa", "reviewer"]
    assert manifest["graph"]["loopPolicy"]["mode"] == "pm-checklist"
    assert manifest["graph"]["controlPolicy"]["mode"] == "pm-checklist"


def test_agent_flow_validation_rejects_cycles_with_paths(tmp_path) -> None:
    flow = sample_flow("Cyclic Flow")
    flow["connections"].append(
        {"id": "reviewer-to-planner", "fromAgentId": "reviewer", "toAgentId": "planner", "fromPort": "success"}
    )
    created = create_agent_flow({"flow": flow}, tmp_path)

    validation = validate_saved_agent_flow(created["id"], tmp_path, selected_start_agent_id="planner")

    assert validation["valid"] is False
    assert any(error["code"] == "cycle_detected" and error["path"] == "connections" for error in validation["errors"])


def test_agent_flow_validation_reports_agent_field_paths(tmp_path) -> None:
    flow = sample_flow("Broken Agent Flow")
    flow["agents"][1]["llm"] = "rules"
    flow["agents"][1]["workPackage"]["expectedOutput"] = ""
    created = create_agent_flow({"flow": flow}, tmp_path)

    validation = validate_saved_agent_flow(created["id"], tmp_path)

    assert validation["valid"] is False
    paths = {error["path"] for error in validation["errors"]}
    assert "agents[1].llm" in paths
    assert "agents[1].workPackage.expectedOutput" in paths


def test_compile_agent_flow_creates_immutable_three_card_manifest(tmp_path) -> None:
    created = create_agent_flow({"flow": sample_flow()}, tmp_path)

    manifest = compile_saved_agent_flow(
        created["id"],
        tmp_path,
        {
            "approval": {"approved": True, "approvedBy": "tester", "approvalId": "approval-test"},
            "runContext": {"taskSummary": "Run the approved task.", "firstPromptSummary": "Planner first."},
        },
    )

    assert manifest["flowId"] == created["id"]
    assert manifest["flowVersion"] == 1
    assert manifest["approval"]["approvalId"] == "approval-test"
    assert manifest["runContext"]["taskSummary"] == "Run the approved task."
    assert manifest["graph"]["executionOrder"] == ["planner", "executor", "reviewer"]
    assert len(manifest["profileSnapshots"]) == 3
    assert manifest["profileSnapshots"][0]["source"]["sourceCardId"] == "planner"
    assert manifest["profileSnapshots"][0]["source"]["approvalId"] == "approval-test"
    assert manifest["profileSnapshots"][1]["runtimePolicy"]["sandboxMode"] == "workspace-write"
    assert "path" in manifest

    changed = sample_flow("Changed Later")
    changed["agents"][0]["name"] = "Renamed Planner"
    update_agent_flow(created["id"], {"flow": changed}, tmp_path)
    assert manifest["profileSnapshots"][0]["displayName"] == "Planner"


def test_compile_agent_flow_supports_one_card_manifest(tmp_path) -> None:
    created = create_agent_flow({"flow": sample_one_card_flow()}, tmp_path)

    manifest = compile_saved_agent_flow(created["id"], tmp_path, {"approval": {"approved": True}})

    assert manifest["graph"]["startAgentId"] == "executor"
    assert manifest["graph"]["executionOrder"] == ["executor"]
    assert len(manifest["profileSnapshots"]) == 1


def test_agent_flow_http_api_crud(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ui, "ROOT", tmp_path)

    handler = ui._OrchestratorUIHandler
    handler.orchestrator = None
    handler.dispatcher_service = None
    handler.web_root = tmp_path
    handler.service_id = "mini-orchestrator"
    server = ui._ThreadedHttpServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    try:
        created = _json_request(f"{base_url}/api/agent-flows", "POST", {"flow": sample_flow()})["flow"]
        flow_id = created["id"]
        assert created["version"] == 1

        listing = _json_request(f"{base_url}/api/agent-flows")["flows"]
        assert listing[0]["id"] == flow_id

        loaded = _json_request(f"{base_url}/api/agent-flows/{flow_id}")["flow"]
        assert loaded["name"] == "Planner Flow"

        replacement = sample_flow("Planner Flow V2")
        updated = _json_request(f"{base_url}/api/agent-flows/{flow_id}", "PUT", {"flow": replacement})["flow"]
        assert updated["version"] == 2
        assert updated["name"] == "Planner Flow V2"

        validation = _json_request(f"{base_url}/api/agent-flows/{flow_id}/validate", "POST", {})
        assert validation["valid"] is True
        assert validation["startNodeCandidates"][0]["agentId"] == "planner"

        manifest = _json_request(
            f"{base_url}/api/agent-flows/{flow_id}/compile",
            "POST",
            {
                "approval": {"approved": True, "approvedBy": "tester"},
                "runContext": {"taskSummary": "HTTP task"},
            },
        )["manifest"]
        assert manifest["flowId"] == flow_id
        assert manifest["runContext"]["taskSummary"] == "HTTP task"
        assert len(manifest["profileSnapshots"]) == 3
    finally:
        server.shutdown()
        server.server_close()


def _json_request(url: str, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"content-type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))
