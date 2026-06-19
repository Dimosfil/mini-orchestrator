from __future__ import annotations

import json
import threading
import urllib.request

import pytest

from mini_orchestrator import ui
from mini_orchestrator.symphony_daemon import (
    SymphonyDaemonError,
    build_symphony_live_runs,
    fetch_symphony_state,
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
