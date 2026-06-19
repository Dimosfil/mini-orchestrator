from __future__ import annotations

import pytest

from mini_orchestrator import worknest_bridge
from mini_orchestrator.worknest_bridge import WorkNestBridgeError, WorkNestLifecycleBridge


def service_record() -> dict:
    return {
        "id": "worknest",
        "capabilities": ["next-task", "task-completion"],
        "endpoints": {
            "api": "http://worknest.test/agent-intake",
            "contract": "http://worknest.test/agent-intake/contract",
        },
    }


def contract() -> dict:
    return {
        "taskMovementPolicy": {
            "externalAgents": [
                "request assigned work through /agent-intake/next-task",
                "submit solutions through /agent-intake/task-completed",
            ]
        }
    }


def test_worknest_bridge_claim_reads_contract_before_next_task(monkeypatch) -> None:
    calls: list[tuple[str, str, dict | None]] = []

    def fake_request(url: str, method: str = "GET", payload: dict | None = None) -> dict:
        calls.append((url, method, payload))
        if url == "http://config.test/services/worknest":
            return service_record()
        if url == "http://worknest.test/agent-intake/contract":
            return contract()
        if url == "http://worknest.test/agent-intake/next-task?project=mini-orchestrator":
            return {
                "task": {
                    "taskId": "task-1",
                    "sprintId": "sprint-1",
                    "project": "mini-orchestrator",
                    "title": "Task",
                    "whatToDo": "Do it",
                    "definitionOfDone": "Done",
                }
            }
        raise AssertionError(url)

    monkeypatch.setattr(worknest_bridge, "_json_request", fake_request)

    bridge = WorkNestLifecycleBridge(config_service_url="http://config.test", service_id="worknest")
    task = bridge.claim_next_task("mini-orchestrator")

    assert task is not None
    assert task.task_id == "task-1"
    assert calls[1][0].endswith("/contract")
    assert calls[2][0].endswith("/next-task?project=mini-orchestrator")


def test_worknest_bridge_complete_is_terminal_and_contract_gated(monkeypatch) -> None:
    calls: list[tuple[str, str, dict | None]] = []

    def fake_request(url: str, method: str = "GET", payload: dict | None = None) -> dict:
        calls.append((url, method, payload))
        if url == "http://config.test/services/worknest":
            return service_record()
        if url == "http://worknest.test/agent-intake/contract":
            return contract()
        if url == "http://worknest.test/agent-intake/task-completed":
            return {"status": "updated"}
        raise AssertionError(url)

    monkeypatch.setattr(worknest_bridge, "_json_request", fake_request)

    bridge = WorkNestLifecycleBridge(config_service_url="http://config.test", service_id="worknest")
    result = bridge.complete_task(
        task_id="task-1",
        sprint_id="sprint-1",
        project="mini-orchestrator",
        status="done",
        summary="Completed.",
        changed_files=["a.py"],
        checks=["pytest"],
    )

    assert result["status"] == "updated"
    assert calls[1][0].endswith("/contract")
    assert calls[2][1] == "POST"
    assert calls[2][2]["status"] == "done"
    assert calls[2][2]["changedFiles"] == ["a.py"]

    with pytest.raises(WorkNestBridgeError):
        bridge.complete_task(
            task_id="task-1",
            sprint_id="sprint-1",
            project="mini-orchestrator",
            status="in_progress",
            summary="Nope.",
        )
