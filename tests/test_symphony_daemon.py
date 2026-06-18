from __future__ import annotations

import json

import pytest

from mini_orchestrator.symphony_daemon import (
    SymphonyDaemonError,
    build_symphony_live_runs,
    fetch_symphony_state,
)
from mini_orchestrator.ui import build_live_runs_payload


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
    assert running["runId"] == "MT-1"
    assert running["currentAgent"] == "executor"
    assert running["tokens"]["total"] == 120
    assert running["stages"][0]["threadId"] == "thread-1"
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


def test_live_runs_payload_falls_back_to_dispatcher_jsonl(tmp_path, monkeypatch):
    def fail():
        raise SymphonyDaemonError("daemon unavailable")

    monkeypatch.setattr("mini_orchestrator.ui.build_symphony_live_runs_from_url", fail)

    payload = build_live_runs_payload(tmp_path)

    assert payload["source"] == "dispatcher-jsonl"
    assert payload["daemonSourceTried"] == "symphony-daemon"
    assert payload["daemonError"] == "daemon unavailable"
