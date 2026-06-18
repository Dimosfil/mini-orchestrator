from __future__ import annotations

import json

from mini_orchestrator.live_runs import build_dispatcher_live_runs


def write_event(log_path, payload):
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def test_dispatcher_live_runs_surface_approval_gate(tmp_path):
    root = tmp_path
    log_path = root / "tools" / "codex-dispatcher" / "runs" / "approval-run.jsonl"
    log_path.parent.mkdir(parents=True)

    write_event(log_path, {"time": "2026-06-18T00:00:00Z", "type": "task_created", "task": "calc", "chain": True})
    write_event(
        log_path,
        {
            "time": "2026-06-18T00:00:01Z",
            "type": "agent_thread_started",
            "agent": "executor",
            "model": "gpt-5.4",
            "threadId": "thread-executor",
        },
    )
    write_event(
        log_path,
        {
            "time": "2026-06-18T00:00:02Z",
            "type": "codex_notification",
            "message": {
                "method": "item/fileChange/requestApproval",
                "params": {"threadId": "thread-executor", "turnId": "turn-1", "itemId": "change-1"},
            },
        },
    )

    payload = build_dispatcher_live_runs(root)

    run = payload["runs"][0]
    assert run["runId"] == "approval-run"
    assert run["status"] == "waiting_approval"
    assert run["currentAgent"] == "executor"
    assert run["approval"]["required"] is True
    assert payload["summary"]["blocked"] == 1


def test_dispatcher_live_runs_surface_completed_chain(tmp_path):
    root = tmp_path
    log_path = root / "tools" / "codex-dispatcher" / "runs" / "done-run.jsonl"
    log_path.parent.mkdir(parents=True)

    write_event(log_path, {"time": "2026-06-18T00:00:00Z", "type": "task_created", "task": "calc", "chain": True})
    write_event(log_path, {"time": "2026-06-18T00:00:01Z", "type": "agent_started", "agent": "planner"})
    write_event(log_path, {"time": "2026-06-18T00:00:02Z", "type": "agent_result", "agent": "planner", "output": "plan"})
    write_event(log_path, {"time": "2026-06-18T00:00:03Z", "type": "agent_started", "agent": "executor"})
    write_event(log_path, {"time": "2026-06-18T00:00:04Z", "type": "agent_result", "agent": "executor", "output": "done"})
    write_event(log_path, {"time": "2026-06-18T00:00:05Z", "type": "agent_started", "agent": "reviewer"})
    write_event(log_path, {"time": "2026-06-18T00:00:06Z", "type": "agent_result", "agent": "reviewer", "output": "ok"})
    write_event(log_path, {"time": "2026-06-18T00:00:07Z", "type": "final"})

    payload = build_dispatcher_live_runs(root)

    run = payload["runs"][0]
    assert run["status"] == "done"
    assert run["currentAgent"] == "reviewer"
    assert run["outputs"]["executor"] == "done"
    assert payload["summary"]["done"] == 1
