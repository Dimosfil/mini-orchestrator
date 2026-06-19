from __future__ import annotations

import json
import threading
import urllib.request

import pytest

from mini_orchestrator import ui
from mini_orchestrator import service_discovery
from mini_orchestrator.symphony_daemon import (
    SymphonyDaemonError,
    build_symphony_live_runs,
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
            "codex_totals": {"total_tokens": 120},
        },
        "http://127.0.0.1:4000/api/v1/state",
    )

    assert payload["source"] == "symphony-daemon"
    assert payload["summary"] == {"total": 3, "active": 2, "blocked": 1, "done": 0, "failed": 0}
    assert [run["status"] for run in payload["runs"]] == ["running", "retrying", "blocked"]
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
    assert [run["runId"] for run in payload["runs"]] == ["latest-dispatcher-chain"]
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


def test_symphony_run_http_endpoint_returns_blocker_without_http_error(tmp_path, monkeypatch):
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
        with urllib.request.urlopen(request, timeout=5) as response:
            body = json.loads(response.read().decode("utf-8"))

        assert response.status == 200
        assert body["status"] == "blocked"
        assert body["code"] == "symphony-intake-missing"
        assert body["accepted"] is False
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
