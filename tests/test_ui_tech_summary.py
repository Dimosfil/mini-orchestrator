from __future__ import annotations

import json

from mini_orchestrator.ui import build_dispatcher_tech_summary


def write_event(log_path, payload):
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def test_dispatcher_tech_summary_compacts_codex_worker_log(tmp_path):
    root = tmp_path
    log_path = root / "tools" / "codex-dispatcher" / "runs" / "run.jsonl"
    log_path.parent.mkdir(parents=True)

    write_event(log_path, {"time": "2026-06-18T00:00:00Z", "type": "app_server_started"})
    write_event(
        log_path,
        {
            "time": "2026-06-18T00:00:01Z",
            "type": "agent_thread_started",
            "agent": "planner",
            "model": "gpt-5.5",
            "threadId": "thread-123",
        },
    )
    write_event(
        log_path,
        {
            "time": "2026-06-18T00:00:02Z",
            "type": "handoff",
            "to": "planner",
            "prompt": "secret prompt body",
        },
    )
    write_event(
        log_path,
        {
            "time": "2026-06-18T00:00:03Z",
            "type": "agent_turn_started",
            "agent": "planner",
            "threadId": "thread-123",
            "turnId": "turn-456",
        },
    )
    write_event(
        log_path,
        {
            "time": "2026-06-18T00:00:04Z",
            "type": "timing",
            "name": "codex_turn_completed",
            "agent": "planner",
            "elapsedSeconds": 1.25,
        },
    )
    write_event(
        log_path,
        {
            "time": "2026-06-18T00:00:05Z",
            "type": "codex_notification",
            "message": {"method": "turn/completed", "params": {"turn": {"id": "turn-456"}}},
        },
    )

    tech = build_dispatcher_tech_summary(
        {
            "log": "tools/codex-dispatcher/runs/run.jsonl",
            "mode": "plan",
            "planOnly": True,
            "durationSeconds": 2.0,
        },
        root,
    )

    assert tech["logStatus"] == "available"
    assert tech["runtime"] == "codex-app-server"
    assert tech["workerVisibility"] == "codex-sidebar-visible"
    assert tech["workers"][0]["threadId"] == "thread-123"
    assert tech["workers"][0]["turnIds"] == ["turn-456"]
    assert tech["timings"][0]["elapsedSeconds"] == 1.25
    assert tech["codexNotifications"]["turn/completed"] == 1
    assert tech["eventTypes"]["handoff"] == 1

    rendered = json.dumps(tech, ensure_ascii=False)
    assert "secret prompt body" not in rendered
    assert "promptChars" in rendered


def test_dispatcher_tech_summary_rejects_log_paths_outside_root(tmp_path):
    outside = tmp_path.parent / "outside.jsonl"
    outside.write_text("{}", encoding="utf-8")

    tech = build_dispatcher_tech_summary({"log": str(outside)}, tmp_path)

    assert tech["logStatus"] == "not-provided"
    assert tech["recentEvents"] == []
