from __future__ import annotations

import json
from pathlib import Path

import pytest

from mini_orchestrator import command_adapter, service_discovery
from mini_orchestrator.cli import run_from_args
from mini_orchestrator.config import OrchestratorConfig, parse_runtime_config
from mini_orchestrator.executor import Executor
from mini_orchestrator.llm import LlmJsonResult, LlmRequestError, OpenAiResponsesClient, _extract_first_json_object
from mini_orchestrator.model_defaults import DEFAULT_COORDINATOR_MODEL, DEFAULT_EXECUTOR_MODEL
from mini_orchestrator.models import TaskAction, TaskState, dump_state_line, state_to_json_payload
from mini_orchestrator.orchestrator import Orchestrator
from mini_orchestrator.planner import Planner
from mini_orchestrator.router import Router
from mini_orchestrator.tools import ToolResult
from mini_orchestrator.validator import Validator


class FakeToolRuntime:
    def __init__(self, result: ToolResult):
        self.result = result
        self.calls: list[tuple[str, dict]] = []

    def execute(self, tool: str, args: dict) -> ToolResult:
        self.calls.append((tool, args))
        return self.result


class FakePlannerClient:
    is_enabled = True
    is_required = False

    def __init__(self, payload: dict):
        self.payload = payload

    def create_json_plan(self, **_kwargs) -> LlmJsonResult:
        return LlmJsonResult(raw_text=json.dumps(self.payload), payload=self.payload)


def test_task_state_serializes_events_and_plan() -> None:
    state = TaskState.new("прочитай README", max_iterations=2, max_retries=1)
    state.plan.append(
        TaskAction(
            action_id="action-1",
            step=0,
            description="Read README",
            tool="read_file",
            args={"path": "README.md"},
            model=DEFAULT_EXECUTOR_MODEL,
        )
    )

    payload = state_to_json_payload(state)
    line = dump_state_line(state, "planner", "готово", {"ключ": "значение"})

    assert payload["goal"] == "прочитай README"
    assert payload["plan"][0]["tool"] == "read_file"
    assert '"готово"' in line
    assert json.loads(line)["details"]["ключ"] == "значение"


def test_router_sends_high_risk_goals_to_coordinator() -> None:
    router = Router()

    assert router.route_goal("run tests").model == DEFAULT_EXECUTOR_MODEL
    decision = router.route_goal("deploy and push release")

    assert decision.model == DEFAULT_COORDINATOR_MODEL
    assert "high-risk" in decision.reason


def test_rule_planner_parses_multi_step_local_actions(tmp_path: Path) -> None:
    planner = Planner(workspace_root=tmp_path)

    plan = planner.plan('read README.md then search "needle" and run python --version')

    assert [action.tool for action in plan.actions] == ["read_file", "search", "run_command"]
    assert plan.actions[0].args["path"] == "README.md"
    assert plan.actions[1].args["query"] == "needle"
    assert plan.actions[2].args["command"] == "python --version"
    assert [action.step for action in plan.actions] == [0, 1, 2]


def test_llm_planner_normalizes_safe_actions_and_discards_bad_ones(tmp_path: Path) -> None:
    planner = Planner(
        workspace_root=tmp_path,
        llm_client=FakePlannerClient(
            {
                "rationale": "safe",
                "actions": [
                    {"description": "Answer", "tool": "respond", "args": {"message": "ok"}},
                    {"description": "Bad", "tool": "delete_everything", "args": {}},
                    {"description": "Search", "tool": "search", "args": {"query": "needle"}},
                ],
            }
        ),
    )

    plan = planner.plan("hello")

    assert [action.tool for action in plan.actions] == ["respond", "search"]
    assert plan.actions[0].model == DEFAULT_COORDINATOR_MODEL
    assert plan.actions[1].args["path"] == str(tmp_path)


def test_executor_delegates_to_tool_runtime() -> None:
    runtime = FakeToolRuntime(ToolResult("respond", True, "hello", {"kind": "direct_response"}))
    action = TaskAction("a1", 0, "Respond", "respond", {"message": "hello"}, "model")

    report = Executor(runtime).run_action(action)  # type: ignore[arg-type]

    assert report.success is True
    assert report.result and report.result.output == "hello"
    assert runtime.calls == [("respond", {"message": "hello"})]


def test_validator_retry_policy_distinguishes_command_and_patch_failures() -> None:
    action = TaskAction("a1", 0, "Run", "run_command", {}, "model")
    timeout_report = Executor(FakeToolRuntime(ToolResult("run_command", False, "", {}, "command timed out"))).run_action(action)  # type: ignore[arg-type]

    timeout_decision = Validator().validate(action, timeout_report)

    assert timeout_decision.need_retry is True

    patch_action = TaskAction("a2", 0, "Patch", "apply_patch", {}, "model")
    patch_report = Executor(FakeToolRuntime(ToolResult("apply_patch", False, "", {}, "old content block was not found"))).run_action(patch_action)  # type: ignore[arg-type]

    patch_decision = Validator().validate(patch_action, patch_report)

    assert patch_decision.need_retry is False


def test_orchestrator_runs_rule_based_read_and_writes_jsonl_log(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("agent rules", encoding="utf-8")
    log_path = tmp_path / ".mini_orchestrator" / "runs" / "orchestrator.log.jsonl"
    config = OrchestratorConfig(
        workspace_root=tmp_path,
        allowed_roots=[tmp_path],
        llm_provider="rules",
        max_iterations=3,
        max_retries=0,
    )

    orchestrator = Orchestrator(config, log_path=log_path)
    state = orchestrator.run("read AGENTS.md")

    assert state.status == "done"
    assert state.completed_steps == 1
    assert state.result["tool_output"] == "agent rules"
    log_lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert [line["stage"] for line in log_lines][:2] == ["router", "router"]
    assert log_lines[-1]["status"] == "done"


def test_parse_runtime_config_uses_environment_and_cli_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    extra_root = tmp_path / "extra"
    extra_root.mkdir()
    monkeypatch.setenv("MINI_ORCHESTRATOR_ALLOWED_ROOTS", str(extra_root))
    monkeypatch.setenv("MINI_ORCHESTRATOR_MAX_ITERATIONS", "9")
    monkeypatch.setenv("MINI_ORCHESTRATOR_MAX_RETRIES", "4")
    monkeypatch.setenv("MINI_ORCHESTRATOR_LLM_PROVIDER", "openai")
    monkeypatch.setenv("MINI_ORCHESTRATOR_COMMAND_OUTPUT_LIMIT", "321")
    monkeypatch.setenv("MINI_ORCHESTRATOR_COORDINATOR_MODEL", "coordinator-test-model")
    monkeypatch.setenv("MINI_ORCHESTRATOR_EXECUTOR_MODEL", "executor-test-model")

    config = parse_runtime_config(str(tmp_path), max_iterations=2, max_retries=None, llm_provider="rules")

    assert config.workspace_root == tmp_path.resolve()
    assert extra_root.resolve() in config.allowed_roots
    assert config.max_iterations == 2
    assert config.max_retries == 4
    assert config.llm_provider == "rules"
    assert config.command_output_limit == 321
    assert config.coordinator_model == "coordinator-test-model"
    assert config.executor_model == "executor-test-model"


def test_command_adapter_blocks_destructive_commands_and_preserves_quoted_args() -> None:
    assert command_adapter.validate_command("git reset --hard") == "blocked potentially destructive command: git reset"

    split = command_adapter.split_command('python -c "print(123)"')

    assert split[0] == "python"
    assert "print(123)" in " ".join(split)


def test_llm_json_helpers_and_request_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert _extract_first_json_object('```json\n{"ok": true}\n```') == {"ok": True}
    assert _extract_first_json_object('prefix {"answer": 1} suffix') == {"answer": 1}
    with pytest.raises(LlmRequestError):
        _extract_first_json_object("no json here")

    config = OrchestratorConfig(workspace_root=tmp_path, allowed_roots=[tmp_path], llm_provider="openai")
    client = OpenAiResponsesClient(config)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    calls: list[dict] = []

    def fake_post(body: dict, _api_key: str) -> dict:
        calls.append(body)
        if len(calls) == 1:
            raise LlmRequestError("OpenAI request failed with HTTP 400: schema unsupported")
        return {"output_text": '{"rationale":"fallback","actions":[]}'}

    monkeypatch.setattr(client, "_post_responses", fake_post)

    result = client.create_json_plan("system", "user", {"type": "object"})

    assert result.payload["rationale"] == "fallback"
    assert "text" in calls[0]
    assert "text" not in calls[1]


def test_service_discovery_resolves_registered_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runtime_config = tmp_path / "service-runtime.json"
    runtime_config.write_text(
        json.dumps(
            {
                "service_id": "mini-orchestrator-ui",
                "self_registration": "off",
                "configServiceUrl": "http://127.0.0.1:4186",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(service_discovery, "RUNTIME_CONFIG_PATH", runtime_config)

    def fake_get_json(url: str) -> dict:
        if url.endswith("/health"):
            return {"ok": True}
        if url.endswith("/services/mini-orchestrator-ui"):
            return {
                "id": "mini-orchestrator-ui",
                "baseUrl": "http://127.0.0.1:8000",
                "endpoints": {"availability": "/health", "api": "/api"},
            }
        raise AssertionError(url)

    monkeypatch.setattr(service_discovery, "_get_json", fake_get_json)

    runtime = service_discovery.resolve_ui_runtime("127.0.0.1", 8000)

    assert runtime.host == "127.0.0.1"
    assert runtime.port == 8000
    assert runtime.base_url == "http://127.0.0.1:8000"
    assert runtime.endpoints["api"] == "/api"


def test_service_discovery_blocks_mismatched_requested_port(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runtime_config = tmp_path / "service-runtime.json"
    runtime_config.write_text(
        '{"service_id":"mini-orchestrator-ui","self_registration":"off","configServiceUrl":"http://127.0.0.1:4186"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(service_discovery, "RUNTIME_CONFIG_PATH", runtime_config)
    monkeypatch.setattr(service_discovery, "_get_json", lambda _url: {
        "id": "mini-orchestrator-ui",
        "baseUrl": "http://127.0.0.1:8000",
        "endpoints": {"availability": "/health", "api": "/api"},
    })

    with pytest.raises(service_discovery.ConfigServiceBlocker) as exc_info:
        service_discovery.resolve_ui_runtime(None, 9000)

    assert "does not match" in str(exc_info.value)


def test_cli_returns_usage_error_without_goal(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = run_from_args(["--no-log"])

    assert exit_code == 1
    assert "usage:" in capsys.readouterr().out


def test_cli_runs_goal_and_prints_final_state(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "AGENTS.md").write_text("rules", encoding="utf-8")

    exit_code = run_from_args(["read AGENTS.md", "--workdir", str(tmp_path), "--llm-provider", "rules", "--no-log"])
    output = capsys.readouterr().out.strip()
    payload = json.loads(output)

    assert exit_code == 0
    assert payload["status"] == "done"
    assert payload["completed_steps"] == 1
