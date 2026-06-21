from __future__ import annotations

from pathlib import Path
from typing import Any

from mini_orchestrator.codex_dispatcher_service import PersistentCodexDispatcher


class FakeCodexServer:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.worker_chat_root = root / "worker-chats"
        self.process_cwd = self.worker_chat_root
        self.started_workers: list[dict[str, Any]] = []
        self.turns: list[dict[str, Any]] = []

    def start_thread(self, worker, developer_instructions=None, access_mode=None):
        self.started_workers.append(
            {
                "name": worker.name,
                "model": worker.model,
                "developerInstructions": developer_instructions,
                "accessMode": access_mode,
            }
        )
        return "thread-visual-task"

    def run_turn(self, thread_id, worker, prompt, effort=None, access_mode=None):
        self.turns.append(
            {
                "threadId": thread_id,
                "workerName": worker.name,
                "prompt": prompt,
                "effort": effort,
                "accessMode": access_mode,
            }
        )
        return "visual agent task done"


def test_visual_agent_task_uses_selected_card_name_as_worker(tmp_path) -> None:
    fake_server = FakeCodexServer(tmp_path)
    service = PersistentCodexDispatcher(
        root=tmp_path,
        runs_dir=tmp_path / "tools" / "codex-dispatcher" / "runs",
    )

    def fake_ensure_server(*_args, **_kwargs):
        return fake_server

    service._ensure_server = fake_ensure_server  # type: ignore[method-assign]

    result = service.run_visual_agent_task(
        {
            "id": "dental-crm-builder",
            "name": "Dental CRM Builder",
            "role": "Executor",
            "llm": "gpt-5.4",
            "reasoning": "medium",
            "accessMode": "workspace-write",
            "workPackage": {"currentObjective": "Build dental CRM demo."},
        },
        "Build dental CRM demo.",
        "worker-profile-dental-crm-builder-test",
    )

    assert result["mode"] == "visual-agent-task"
    assert fake_server.started_workers[0]["name"] == "Dental CRM Builder"
    assert fake_server.turns[0]["workerName"] == "Dental CRM Builder"
    assert result["agents"]["Dental CRM Builder"] == "visual agent task done"


def test_visual_agent_task_requires_card_model(tmp_path) -> None:
    service = PersistentCodexDispatcher(
        root=tmp_path,
        runs_dir=tmp_path / "tools" / "codex-dispatcher" / "runs",
    )

    try:
        service.run_visual_agent_task(
            {
                "id": "reviewer",
                "name": "Reviewer",
                "role": "Reviewer",
                "reasoning": "high",
                "accessMode": "workspace-write",
            },
            "Review the result.",
            "worker-profile-reviewer-test",
        )
    except ValueError as exc:
        assert "missing an explicit llm setting" in str(exc)
    else:
        raise AssertionError("visual agent task accepted a card without llm")
