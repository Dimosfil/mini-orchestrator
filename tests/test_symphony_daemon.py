from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from types import SimpleNamespace

import pytest

from mini_orchestrator import ui
from mini_orchestrator import service_discovery
from mini_orchestrator import runtime_store
from mini_orchestrator.symphony_daemon import (
    SymphonyDaemonError,
    build_symphony_intake_payload,
    build_local_symphony_gateway_runs,
    build_symphony_live_runs,
    create_symphony_gateway_run,
    configured_state_url,
    fetch_symphony_state,
    fetch_symphony_issue,
    refresh_symphony_state,
)
from mini_orchestrator.ui import build_live_runs_payload, build_symphony_run_blocker


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.headers = self

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get_content_charset(self):
        return "utf-8"

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def executable_agent(agent_id: str, name: str, role: str, *, model: str = "gpt-5.5") -> dict:
    return {
        "id": agent_id,
        "name": name,
        "role": role,
        "preset": role.lower(),
        "llm": model,
        "reasoning": "medium",
        "accessMode": "workspace-write",
        "workPackage": {
            "instructions": f"Act as {role}.",
            "currentObjective": "Complete this stage.",
            "inputsArtifacts": "Task and previous outputs.",
            "constraints": "Stay in scope.",
            "previousOutputs": "Use prior outputs.",
            "allowedTools": "Use approved tools.",
            "expectedOutput": "Stage result.",
        },
    }


def executable_chain(*agents: dict) -> dict:
    selected_agents = list(agents) or [
        executable_agent("planner", "Planner", "Planner"),
        executable_agent("executor", "Executor", "Executor", model="gpt-5.3-codex-spark"),
        executable_agent("reviewer", "Reviewer", "Reviewer"),
    ]
    connections = [
        {
            "id": f"{selected_agents[index]['id']}-to-{selected_agents[index + 1]['id']}",
            "fromAgentId": selected_agents[index]["id"],
            "toAgentId": selected_agents[index + 1]["id"],
            "fromPort": "success",
        }
        for index in range(len(selected_agents) - 1)
    ]
    return {
        "id": "chain-1",
        "name": "Executable chain",
        "updatedAt": "2026-06-24T00:00:00Z",
        "flow": {"agents": selected_agents, "connections": connections},
    }


def test_symphony_state_maps_runtime_entries_to_live_runs():
    payload = build_symphony_live_runs(
        {
            "generated_at": "2026-06-18T20:51:25Z",
            "running": [
                {
                    "issue_id": "issue-1",
                    "issue_identifier": "MT-1",
                    "issue_url": "https://tracker.example/MT-1",
                    "state": "In Progress",
                    "worker_host": "executor",
                    "workspace_path": "workspace/MT-1",
                    "session_id": "thread-1",
                    "turn_count": 2,
                    "last_event": "turn_completed",
                    "started_at": "2026-06-18T20:50:00Z",
                    "last_event_at": "2026-06-18T20:51:00Z",
                    "tokens": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
                }
            ],
            "retrying": [
                {
                    "issue_id": "issue-2",
                    "issue_identifier": "MT-2",
                    "attempt": 3,
                    "due_at": "2026-06-18T20:55:00Z",
                    "error": "no available slots",
                }
            ],
            "blocked": [
                {
                    "issue_id": "issue-3",
                    "issue_identifier": "MT-3",
                    "state": "Human Review",
                    "error": "approval required",
                    "blocked_at": "2026-06-18T20:52:00Z",
                }
            ],
            "completed": [
                {
                    "issue_id": "issue-4",
                    "issue_identifier": "MT-4",
                    "issue_url": "https://tracker.example/MT-4",
                    "state": "Done",
                    "workspace_path": "workspace/MT-4",
                    "session_id": "thread-4",
                    "turn_count": 1,
                    "last_event": "turn_completed",
                    "last_message": "turn completed (completed)",
                    "started_at": "2026-06-18T20:53:00Z",
                    "completed_at": "2026-06-18T20:54:00Z",
                    "last_event_at": "2026-06-18T20:54:00Z",
                    "tokens": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
                }
            ],
            "codex_totals": {"total_tokens": 120},
        },
        "http://127.0.0.1:4000/api/v1/state",
    )

    assert payload["source"] == "symphony-daemon"
    assert payload["summary"] == {"total": 4, "active": 2, "blocked": 1, "done": 1, "failed": 0, "stale": 0}
    assert [run["status"] for run in payload["runs"]] == ["running", "retrying", "blocked", "done", "running"]
    running = payload["runs"][0]
    assert running["schemaVersion"] == 1
    assert running["runId"] == "MT-1"
    assert running["sourceLabel"] == "Symphony"
    assert running["currentAgent"] == "executor"
    assert running["tokens"]["total"] == 120
    assert running["stages"][0]["threadId"] == "thread-1"
    assert running["stale"]["isStale"] is False
    blocked = payload["runs"][2]
    assert blocked["approval"]["required"] is True
    assert blocked["lastError"] == "approval required"
    done = payload["runs"][3]
    assert done["runId"] == "MT-4"
    assert done["status"] == "done"
    assert done["stages"][0]["completedAt"] == "2026-06-18T20:54:00Z"
    summary = payload["runs"][4]
    assert summary["runId"] == "symphony-daemon-summary"
    assert summary["daemonSnapshot"]["counts"] == {"running": 1, "retrying": 1, "blocked": 1, "total": 3}


def test_symphony_state_json_error_raises(monkeypatch):
    def fake_urlopen(_request, timeout):
        assert timeout == 2.0
        return FakeResponse({"error": {"code": "snapshot_timeout", "message": "Snapshot timed out"}})

    monkeypatch.setattr("mini_orchestrator.symphony_daemon.urlopen", fake_urlopen)

    with pytest.raises(SymphonyDaemonError, match="Snapshot timed out"):
        fetch_symphony_state("http://daemon/state")


def test_configured_state_url_prefers_explicit_environment(monkeypatch):
    monkeypatch.setenv("MINI_ORCHESTRATOR_DAEMON_STATE_URL", "http://example.test/custom-state")

    def fail(_service_id):
        raise AssertionError("explicit daemon state URL should skip config-service")

    monkeypatch.setattr(service_discovery, "resolve_service_runtime", fail)

    assert configured_state_url() == "http://example.test/custom-state"


def test_configured_state_url_resolves_symphony_service_record(monkeypatch):
    monkeypatch.delenv("MINI_ORCHESTRATOR_DAEMON_STATE_URL", raising=False)
    monkeypatch.delenv("MINI_ORCHESTRATOR_SYMPHONY_SERVICE_ID", raising=False)

    def fake_resolve(service_id):
        assert service_id == "symphony"
        return service_discovery.ResolvedServiceRuntime(
            service_id="symphony",
            base_url="http://127.0.0.1:4000",
            config_service_url="http://127.0.0.1:4100",
            endpoints={"availability": "/api/v1/state", "api": "/api/v1"},
            record={},
        )

    monkeypatch.setattr(service_discovery, "resolve_service_runtime", fake_resolve)

    assert configured_state_url() == "http://127.0.0.1:4000/api/v1/state"


def test_refresh_and_issue_use_symphony_api_endpoint(monkeypatch):
    monkeypatch.delenv("MINI_ORCHESTRATOR_DAEMON_STATE_URL", raising=False)
    calls = []

    def fake_resolve(service_id):
        assert service_id == "symphony"
        return service_discovery.ResolvedServiceRuntime(
            service_id="symphony",
            base_url="http://symphony.test/root",
            config_service_url="http://config.test",
            endpoints={"availability": "/api/v1/state", "api": "/api/v1"},
            record={},
        )

    def fake_urlopen(request, timeout):
        calls.append((request.full_url, request.get_method(), timeout))
        return FakeResponse({"ok": True})

    monkeypatch.setattr(service_discovery, "resolve_service_runtime", fake_resolve)
    monkeypatch.setattr("mini_orchestrator.symphony_daemon.urlopen", fake_urlopen)

    assert refresh_symphony_state() == {"ok": True}
    assert fetch_symphony_issue("MT 1") == {"ok": True}
    assert calls == [
        ("http://symphony.test/root/api/v1/refresh", "POST", 5.0),
        ("http://symphony.test/root/api/v1/MT%201", "GET", 5.0),
    ]


def write_event(log_path, payload):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_dispatcher_chain(root, run_id="dispatcher-run"):
    log_path = root / "tools" / "codex-dispatcher" / "runs" / f"{run_id}.jsonl"
    write_event(log_path, {"time": "2026-06-18T00:00:00Z", "type": "task_created", "task": "calc", "chain": True})
    write_event(log_path, {"time": "2026-06-18T00:00:01Z", "type": "agent_started", "agent": "planner"})
    return log_path


def test_combined_live_runs_keeps_dispatcher_jsonl_when_symphony_unavailable(tmp_path, monkeypatch):
    def fail():
        raise SymphonyDaemonError("daemon unavailable")

    monkeypatch.setattr("mini_orchestrator.ui.build_symphony_live_runs_from_url", fail)
    write_dispatcher_chain(tmp_path, "latest-dispatcher-chain")

    payload = build_live_runs_payload(tmp_path)

    assert payload["sourceMode"] == "combined"
    assert payload["daemonSourceTried"] == "symphony-daemon"
    assert payload["daemonError"] == "daemon unavailable"
    assert [run["runId"] for run in payload["runs"]] == ["latest-dispatcher-chain"]
    assert payload["runs"][0]["sourceLabel"] == "Dispatcher"


def test_combined_live_runs_keeps_dispatcher_jsonl_when_symphony_is_empty(tmp_path, monkeypatch):
    def empty_symphony():
        return build_symphony_live_runs(
            {"generated_at": "2026-06-18T00:00:02Z", "running": [], "retrying": [], "blocked": []},
            "http://daemon/state",
        )

    monkeypatch.setattr("mini_orchestrator.ui.build_symphony_live_runs_from_url", empty_symphony)
    write_dispatcher_chain(tmp_path, "latest-dispatcher-chain")

    payload = build_live_runs_payload(tmp_path, "combined")

    assert payload["sourceMode"] == "combined"
    assert payload["summary"]["total"] == 1
    assert [run["runId"] for run in payload["runs"]] == ["symphony-daemon-summary", "latest-dispatcher-chain"]
    assert payload["sources"]["symphony"]["summary"]["total"] == 0


def test_dispatcher_mode_ignores_symphony_failure(tmp_path, monkeypatch):
    def fail():
        raise AssertionError("dispatcher mode should not fetch Symphony")

    monkeypatch.setattr("mini_orchestrator.ui.build_symphony_live_runs_from_url", fail)
    write_dispatcher_chain(tmp_path, "dispatcher-only")

    payload = build_live_runs_payload(tmp_path, "dispatcher")

    assert payload["sourceMode"] == "dispatcher"
    assert [run["runId"] for run in payload["runs"]] == ["dispatcher-only"]
    assert payload["runs"][0]["sourceLabel"] == "Dispatcher"


def test_symphony_mode_reports_error_without_dispatcher_fallback(tmp_path, monkeypatch):
    def fail():
        raise SymphonyDaemonError("daemon unavailable")

    monkeypatch.setattr("mini_orchestrator.ui.build_symphony_live_runs_from_url", fail)
    write_dispatcher_chain(tmp_path, "hidden-in-symphony-mode")

    payload = build_live_runs_payload(tmp_path, "symphony")

    assert payload["sourceMode"] == "symphony"
    assert payload["summary"]["total"] == 0
    assert payload["runs"] == []
    assert payload["daemonError"] == "daemon unavailable"


def test_symphony_run_blocker_validates_approved_task_payload():
    blocker = build_symphony_run_blocker(
        {
            "approved": True,
            "project": "mini-orchestrator",
            "task": {
                "taskId": "task-1",
                "sprintId": "sprint-1",
                "title": "Bridge task",
            },
        }
    )

    assert blocker["status"] == "blocked"
    assert blocker["code"] == "symphony-intake-missing"
    assert blocker["accepted"] is False
    assert blocker["task"]["taskId"] == "task-1"
    assert blocker["requiredContract"]["serviceId"] == "symphony"


def test_symphony_gateway_run_preserves_chain_and_is_listed(tmp_path):
    run = create_symphony_gateway_run(
        tmp_path,
        {
            "approved": True,
            "project": "mini-orchestrator",
            "task": {"taskId": "task-1", "sprintId": "sprint-1", "title": "Bridge task"},
            "chainPreset": executable_chain(),
        },
        {"stateUrl": "http://daemon/state", "summary": {"total": 0}},
    )

    assert run["status"] == "blocked"
    assert run["mode"] == "symphony-gateway"
    assert run["chainPreset"]["id"] == "chain-1"
    assert [stage["label"] for stage in run["stages"]] == ["Planner", "Executor", "Reviewer"]

    payload = build_local_symphony_gateway_runs(tmp_path)

    assert payload["summary"]["blocked"] == 1
    assert payload["runs"][0]["runId"] == run["runId"]
    assert run["symphony"]["intakePayload"]["dispatchStrategy"] == "one-symphony-agent-per-preset-stage"


def test_symphony_intake_payload_expands_preset_agents():
    payload = build_symphony_intake_payload(
        {
            "approved": True,
            "project": "mini-orchestrator",
            "task": "Build the requested release web app",
            "chainPreset": executable_chain(
                {**executable_agent("planner", "Planner", "Planner"), "reasoning": "high", "accessMode": "read-only"},
                {
                    **executable_agent("executor", "Executor", "Executor", model="gpt-5.3-codex-spark"),
                    "accessMode": "danger-full-access",
                },
            ),
        }
    )

    assert payload["schemaVersion"] == "mini-orchestrator.symphony-intake.v1"
    assert payload["dispatchStrategy"] == "one-symphony-agent-per-preset-stage"
    assert [item["agent"]["id"] for item in payload["agentTasks"]] == ["planner", "executor"]
    assert payload["agentTasks"][0]["codex"]["model"] == "gpt-5.5"
    assert payload["agentTasks"][1]["codex"]["accessMode"] == "danger-full-access"
    assert payload["agentTasks"][1]["task"]["global"]["title"] == "Build the requested release web app"


def test_symphony_gateway_run_submits_when_intake_contract_exists(tmp_path, monkeypatch):
    calls = []

    def fake_resolve(service_id):
        assert service_id == "symphony"
        return service_discovery.ResolvedServiceRuntime(
            service_id="symphony",
            base_url="http://symphony.test",
            config_service_url="http://config.test",
            endpoints={
                "availability": "/api/v1/state",
                "api": "/api/v1",
                "contract": "/agent/contract",
                "taskIntake": "/agent-intake/tasks",
            },
            record={},
        )

    def fake_urlopen(request, timeout):
        body = None
        if request.data:
            body = json.loads(request.data.decode("utf-8"))
        calls.append((request.full_url, request.get_method(), timeout, body))
        if request.full_url.endswith("/agent/contract"):
            return FakeResponse({"capabilities": ["task-intake"]})
        if request.full_url.endswith("/agent-intake/tasks"):
            return FakeResponse({"status": "queued", "externalRunId": "sym-run-1"})
        raise AssertionError(request.full_url)

    monkeypatch.setattr(service_discovery, "resolve_service_runtime", fake_resolve)
    monkeypatch.setattr("mini_orchestrator.symphony_daemon.urlopen", fake_urlopen)

    run = create_symphony_gateway_run(
        tmp_path,
        {
            "approved": True,
            "project": "mini-orchestrator",
            "task": "Bridge task",
            "chainPreset": executable_chain(
                executable_agent("planner", "Planner", "Planner"),
                executable_agent("executor", "Executor", "Executor", model="gpt-5.3-codex-spark"),
            ),
        },
        {"stateUrl": "http://daemon/state", "summary": {"total": 0}},
        submit=True,
    )

    assert run["status"] == "queued"
    assert run["lastError"] == ""
    assert run["symphony"]["intakeSubmitted"] is True
    assert calls[0][:3] == ("http://symphony.test/agent/contract", "GET", 5.0)
    assert calls[1][0] == "http://symphony.test/agent-intake/tasks"
    assert calls[1][1] == "POST"
    assert [item["agent"]["id"] for item in calls[1][3]["agentTasks"]] == ["planner", "executor"]


def test_symphony_gateway_run_marks_missing_old_queued_intake_stale(tmp_path, monkeypatch):
    def fake_resolve(service_id):
        assert service_id == "symphony"
        return service_discovery.ResolvedServiceRuntime(
            service_id="symphony",
            base_url="http://symphony.test",
            config_service_url="http://config.test",
            endpoints={
                "availability": "/api/v1/state",
                "api": "/api/v1",
                "contract": "/agent/contract",
                "taskIntake": "/agent-intake/tasks",
            },
            record={},
        )

    def fake_urlopen(request, timeout):
        if request.full_url.endswith("/agent/contract"):
            return FakeResponse({"capabilities": ["task-intake"]})
        if request.full_url.endswith("/agent-intake/tasks"):
            return FakeResponse(
                {
                    "status": "queued",
                    "request_id": "request-old",
                    "accepted": [
                        {
                            "identifier": "MO-request-old-1-planner",
                            "issue_id": "mini-orchestrator:request-old:1:planner",
                        }
                    ],
                }
            )
        raise AssertionError(request.full_url)

    monkeypatch.setattr(service_discovery, "resolve_service_runtime", fake_resolve)
    monkeypatch.setattr("mini_orchestrator.symphony_daemon.urlopen", fake_urlopen)

    run = create_symphony_gateway_run(tmp_path, {"approved": True, "task": "Old queued task"}, submit=True)
    run["createdAt"] = "2026-06-21T16:00:37+00:00"
    run["updatedAt"] = "2026-06-21T16:00:37+00:00"
    runtime_store.upsert_json_document(tmp_path, "symphony_runs", run["runId"], run)
    daemon_payload = build_symphony_live_runs(
        {"generated_at": "2026-06-22T20:44:43Z", "running": [], "retrying": [], "blocked": [], "completed": []},
        "http://daemon/state",
    )

    payload = build_local_symphony_gateway_runs(tmp_path, daemon_payload)
    stale_run = payload["runs"][0]
    persisted = runtime_store.get_json_document(tmp_path, "symphony_runs", run["runId"])

    assert payload["summary"]["active"] == 0
    assert payload["summary"]["stale"] == 1
    assert stale_run["status"] == "stale"
    assert stale_run["stale"]["isStale"] is True
    assert stale_run["stages"][0]["status"] == "stale"
    assert persisted is not None
    assert persisted["status"] == "stale"


def test_symphony_run_http_endpoint_returns_gateway_run_without_http_error(tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "ROOT", tmp_path)
    monkeypatch.setattr(
        ui,
        "build_symphony_live_runs_from_url",
        lambda: build_symphony_live_runs(
            {"generated_at": "2026-06-18T00:00:02Z", "running": [], "retrying": [], "blocked": []},
            "http://daemon/state",
        ),
    )
    monkeypatch.setattr(
        "mini_orchestrator.symphony_daemon.submit_symphony_intake",
        lambda _payload: (_ for _ in ()).throw(SymphonyDaemonError("symphony-intake-missing")),
    )

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
        payload = {
            "approved": True,
            "task": {
                "taskId": "task-1",
                "sprintId": "sprint-1",
                "title": "Bridge task",
            },
        }
        request = urllib.request.Request(
            f"{base_url}/api/symphony/runs",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"content-type": "application/json; charset=utf-8"},
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(request, timeout=5)

        assert exc_info.value.code == 400
        body = json.loads(exc_info.value.read().decode("utf-8"))
        assert "chainPreset" in body["error"]
    finally:
        server.shutdown()
        server.server_close()


def test_symphony_daemon_runs_inherit_models_from_gateway_outputs():
    daemon_payload = build_symphony_live_runs(
        {
            "generated_at": "2026-06-18T00:00:02Z",
            "running": [],
            "retrying": [],
            "blocked": [],
            "completed": [
                {
                    "issue_id": "mini-orchestrator:crm-smoke-planner",
                    "issue_identifier": "MO-crm-smoke-planner",
                    "last_event": "turn_completed",
                    "tokens": {"total_tokens": 42},
                }
            ],
        },
        "http://daemon/state",
    )
    gateway_payload = {
        "runs": [
            {
                "symphony": {
                    "intakePayload": {
                        "agentTasks": [
                            {
                                "agent": {"id": "crm-smoke-planner", "name": "Planner"},
                                "codex": {"model": "gpt-5.5"},
                            }
                        ]
                    },
                    "miniOwnedChain": {
                        "outputs": [
                            {
                                "agentId": "crm-smoke-planner",
                                "issues": [
                                    {
                                        "issue_id": "mini-orchestrator:crm-smoke-planner",
                                        "issue_identifier": "MO-crm-smoke-planner",
                                    }
                                ],
                            }
                        ]
                    },
                }
            }
        ]
    }

    ui._enrich_symphony_daemon_models(daemon_payload, gateway_payload)

    run = next(item for item in daemon_payload["runs"] if item["runId"] == "MO-crm-smoke-planner")
    assert run["currentAgent"] == "Planner"
    assert run["model"] == "gpt-5.5"
    assert run["stages"][0]["agent"] == "Planner"
    assert run["stages"][0]["model"] == "gpt-5.5"


def test_symphony_daemon_infers_agent_role_and_model_from_mini_issue_id():
    payload = build_symphony_live_runs(
        {
            "generated_at": "2026-06-18T00:00:02Z",
            "running": [],
            "retrying": [],
            "blocked": [],
            "completed": [
                {
                    "issue_id": "mini-orchestrator:release-rerun:1:chain-default-executor",
                    "issue_identifier": "MO-release-rerun-1-chain-default-executor",
                    "issue_url": "mini-orchestrator://release-rerun/chain-default-executor",
                    "last_event": "turn_completed",
                    "tokens": {"total_tokens": 42},
                }
            ],
        },
        "http://daemon/state",
    )

    run = next(item for item in payload["runs"] if item["runId"] == "MO-release-rerun-1-chain-default-executor")
    assert run["currentAgent"] == "Executor"
    assert run["model"] == "gpt-5.3-codex-spark"
    assert run["stages"][0]["agent"] == "Executor"
    assert run["stages"][0]["model"] == "gpt-5.3-codex-spark"


def test_symphony_run_http_endpoint_can_run_mini_owned_chain(tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "ROOT", tmp_path)
    monkeypatch.setattr(
        ui,
        "build_symphony_live_runs_from_url",
        lambda: build_symphony_live_runs(
            {"generated_at": "2026-06-18T00:00:02Z", "running": [], "retrying": [], "blocked": []},
            "http://daemon/state",
        ),
    )

    class FakeGateway:
        def run_mini_owned_chain(self, payload, *, state_url, timeout_per_step_seconds, poll_interval_seconds):
            assert payload["task"] == "Bridge task"
            assert state_url == "http://daemon/state"
            return SimpleNamespace(
                status="done",
                request_id="request-planner,request-executor",
                checklist=[{"id": "item-1", "index": 0, "title": "Bridge task", "status": "done"}],
                outputs=[
                    {"agentId": "planner", "agentName": "Planner", "summary": "Plan ready"},
                    {"agentId": "executor", "agentName": "Executor", "summary": "Build ready"},
                ],
                steps=[
                    {
                        "agentIndex": 0,
                        "agent": {"id": "planner", "name": "Planner"},
                        "requestId": "request-planner",
                        "status": "done",
                        "message": "planner done",
                    },
                    {
                        "agentIndex": 1,
                        "agent": {"id": "executor", "name": "Executor"},
                        "requestId": "request-executor",
                        "status": "done",
                        "message": "executor done",
                    },
                ],
                message="Mini chain done",
            )

    monkeypatch.setattr(ui, "SymphonyGateway", FakeGateway)

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
        payload = {
            "approved": True,
            "task": "Bridge task",
            "waitForCompletion": True,
            "chainPreset": executable_chain(
                executable_agent("planner", "Planner", "Planner"),
                executable_agent("executor", "Executor", "Executor"),
            ),
        }
        request = urllib.request.Request(
            f"{base_url}/api/symphony/runs",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"content-type": "application/json; charset=utf-8"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            body = json.loads(response.read().decode("utf-8"))

        assert response.status == 201
        assert body["status"] == "done"
        assert body["taskCard"]["chainOwner"] == "mini-orchestrator"
        assert body["taskCard"]["checklist"][0]["status"] == "done"
        assert body["symphony"]["miniOwnedChain"]["outputs"][1]["summary"] == "Build ready"
    finally:
        server.shutdown()
        server.server_close()


def test_symphony_refresh_and_issue_http_endpoints_proxy_adapter(tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "ROOT", tmp_path)
    monkeypatch.setattr(ui, "refresh_symphony_state", lambda: {"status": "refresh_requested"})
    monkeypatch.setattr(ui, "fetch_symphony_issue", lambda identifier: {"issue": {"identifier": identifier}})

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
        request = urllib.request.Request(
            f"{base_url}/api/symphony/refresh",
            data=b"{}",
            method="POST",
            headers={"content-type": "application/json; charset=utf-8"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            refresh_body = json.loads(response.read().decode("utf-8"))

        with urllib.request.urlopen(f"{base_url}/api/symphony/issues/MT%201", timeout=5) as response:
            issue_body = json.loads(response.read().decode("utf-8"))

        assert refresh_body == {"status": "refresh_requested"}
        assert issue_body == {"issue": {"identifier": "MT 1"}}
    finally:
        server.shutdown()
        server.server_close()
