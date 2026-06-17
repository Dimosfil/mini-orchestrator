from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mini_orchestrator.agent_api import AgentApiError, VisualAgentApi


def test_agent_chat_rejects_rules_model() -> None:
    api = VisualAgentApi(lambda _args, _timeout: {}, lambda _result: "")

    with pytest.raises(AgentApiError) as exc_info:
        api.chat({"agent": {"llm": "rules"}, "message": "hello"})

    assert exc_info.value.status == 400
    assert "rules fallback" in exc_info.value.message


def test_agent_chat_runs_dispatcher_with_task_file_and_model() -> None:
    calls: list[tuple[list[str], int]] = []

    def run_dispatcher(args: list[str], timeout: int) -> dict[str, Any]:
        calls.append((args, timeout))
        task_file = Path(args[args.index("--task-file") + 1])
        task = task_file.read_text(encoding="utf-8")
        assert "orchestrator executor" in task
        assert "Agent name: Executor 1" in task
        assert "constraints: Stay focused." in task
        assert "User message:\nПривет" in task
        return {
            "mode": "single",
            "log": "tools/codex-dispatcher/runs/test.jsonl",
            "dispatchDecision": {"worker": "executor"},
            "agents": {"executor": "Готово"},
        }

    api = VisualAgentApi(run_dispatcher, lambda _result: "")
    response = api.chat(
        {
            "agent": {
                "name": "Executor 1",
                "role": "Executor",
                "llm": "gpt-5.4",
                "speed": "balanced",
                "reasoning": "medium",
                "workPackage": {"constraints": "Stay focused."},
            },
            "message": "Привет",
            "history": [{"speaker": "user", "text": "Before"}],
        }
    )

    assert response.payload["message"] == "Готово"
    assert response.payload["agent"]["llm"] == "gpt-5.4"
    assert calls
    args, timeout = calls[0]
    assert timeout == 150
    assert "--use-worker-models" in args
    assert "--model" in args
    assert args[args.index("--model") + 1] == "gpt-5.4"


def test_agent_chat_reports_empty_dispatcher_response_detail() -> None:
    api = VisualAgentApi(
        lambda _args, _timeout: {"agents": {"planner": ""}},
        lambda _result: "codex detail",
    )

    with pytest.raises(AgentApiError) as exc_info:
        api.chat({"agent": {"llm": "gpt-5.5"}, "message": "hello"})

    assert exc_info.value.status == 502
    assert "codex detail" in exc_info.value.message


def test_work_package_translation_rejects_empty_text() -> None:
    api = VisualAgentApi(lambda _args, _timeout: {}, lambda _result: "")

    with pytest.raises(AgentApiError) as exc_info:
        api.translate_work_package({"text": "   ", "language": "ru"})

    assert exc_info.value.status == 400
    assert "text" in exc_info.value.message


def test_work_package_translation_uses_dispatcher_and_default_model_for_rules() -> None:
    calls: list[tuple[list[str], int]] = []

    def run_dispatcher(args: list[str], timeout: int) -> dict[str, Any]:
        calls.append((args, timeout))
        task_file = Path(args[args.index("--task-file") + 1])
        task = task_file.read_text(encoding="utf-8")
        assert "Translate one mini-orchestrator work-package field" in task
        assert "Field: role/instructions" in task
        assert "hello world" in task
        return {"agents": {"planner": "Russian: Привет, мир"}}

    api = VisualAgentApi(run_dispatcher, lambda _result: "")
    response = api.translate_work_package(
        {
            "text": "hello world",
            "language": "ru",
            "field": "role/instructions",
            "model": "rules",
        }
    )

    assert response.payload["text"] == "Привет, мир"
    assert response.payload["source"] == "agent"
    assert calls
    args, timeout = calls[0]
    assert timeout == 150
    assert args[args.index("--model") + 1] == "gpt-5.4-mini"


def test_work_package_translation_prefers_direct_translator() -> None:
    dispatcher_calls = 0

    def run_dispatcher(_args: list[str], _timeout: int) -> dict[str, Any]:
        nonlocal dispatcher_calls
        dispatcher_calls += 1
        return {"agents": {"planner": "slow"}}

    api = VisualAgentApi(
        run_dispatcher,
        lambda _result: "",
        lambda text, _language, field: f"{field}:{text}",
    )
    response = api.translate_work_package(
        {
            "text": "hello",
            "language": "ru",
            "field": "role/instructions",
            "model": "gpt-5.5",
        }
    )

    assert response.payload["text"] == "role/instructions:hello"
    assert response.payload["source"] == "openai-direct"
    assert dispatcher_calls == 0


def test_work_package_translation_falls_back_when_direct_translator_fails() -> None:
    def run_dispatcher(_args: list[str], _timeout: int) -> dict[str, Any]:
        return {"agents": {"planner": "fallback translation"}}

    api = VisualAgentApi(
        run_dispatcher,
        lambda _result: "",
        lambda _text, _language, _field: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    response = api.translate_work_package(
        {"text": "hello", "language": "ru", "field": "role/instructions"}
    )

    assert response.payload["text"] == "fallback translation"
    assert response.payload["source"] == "agent"
