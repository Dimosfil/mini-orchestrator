from __future__ import annotations

from mini_orchestrator.daemon_runs import build_demo_daemon_runs


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
    assert run["status"] in {"queued", "claimed", "running", "blocked", "retrying", "done", "failed"}
    assert run["tokens"]["total"] == run["tokens"]["input"] + run["tokens"]["output"]
    assert run["artifacts"]["eventLogPath"].endswith(".jsonl")
