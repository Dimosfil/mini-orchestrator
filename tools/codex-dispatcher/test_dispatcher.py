from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import dispatcher
from cli import DEFAULT_TURN_TIMEOUT_SECONDS, default_turn_timeout_seconds
from codex_app import CodexAppServer
from mini_orchestrator.model_defaults import DEFAULT_COORDINATOR_MODEL, DEFAULT_EXECUTOR_MODEL


class FakeCodexAppServer:
    prompts: list[str] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def __enter__(self) -> "FakeCodexAppServer":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        pass

    def start_thread(self, worker: dispatcher.Worker) -> str:
        return f"thread-{worker.name}"

    def run_turn(self, thread_id: str, worker: dispatcher.Worker, prompt: str, **_kwargs: object) -> str:
        self.prompts.append(prompt)
        if "User task:" in prompt:
            task = prompt.split("User task:", 1)[1].strip().splitlines()[0]
        else:
            task = prompt.split("Current task:", 1)[1].strip().splitlines()[0]
        return f"agent output from {worker.name}: {task}"


class DispatchDecisionTests(unittest.TestCase):
    def test_cli_default_turn_timeout_is_release_chain_sized(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(default_turn_timeout_seconds(), DEFAULT_TURN_TIMEOUT_SECONDS)
        self.assertGreaterEqual(DEFAULT_TURN_TIMEOUT_SECONDS, 300)

    def test_cli_turn_timeout_env_override_is_validated(self) -> None:
        with patch.dict(os.environ, {"MINI_ORCHESTRATOR_DISPATCHER_TURN_TIMEOUT_SECONDS": "450"}):
            self.assertEqual(default_turn_timeout_seconds(), 450)

        with patch.dict(os.environ, {"MINI_ORCHESTRATOR_DISPATCHER_TURN_TIMEOUT_SECONDS": "0"}):
            with self.assertRaisesRegex(ValueError, "greater than 0"):
                default_turn_timeout_seconds()

    def test_codex_app_server_default_turn_timeout_matches_cli_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            server = CodexAppServer(root / "run.jsonl", root=root)

        self.assertEqual(server.turn_timeout_seconds, DEFAULT_TURN_TIMEOUT_SECONDS)

    def test_default_workers_use_shared_model_defaults_and_env_overrides(self) -> None:
        workers = dispatcher.default_workers(dispatcher.ROOT)

        self.assertEqual([worker.model for worker in workers[:2]], [DEFAULT_COORDINATOR_MODEL, DEFAULT_EXECUTOR_MODEL])

        with patch.dict(
            os.environ,
            {
                "MINI_ORCHESTRATOR_COORDINATOR_MODEL": "coordinator-test-model",
                "MINI_ORCHESTRATOR_EXECUTOR_MODEL": "executor-test-model",
                "MINI_ORCHESTRATOR_REVIEWER_MODEL": "reviewer-test-model",
            },
        ):
            overridden = dispatcher.default_workers(dispatcher.ROOT)

        self.assertEqual(
            [worker.model for worker in overridden],
            ["coordinator-test-model", "executor-test-model", "reviewer-test-model"],
        )

    def test_planner_directed_task_routes_to_planner(self) -> None:
        decision = dispatcher.decide_dispatch(
            "Plan the next smallest improvement to the dispatcher",
            dispatcher.WORKERS,
        )

        self.assertEqual(decision.role, "planner")
        self.assertEqual(decision.next_input, "Plan the next smallest improvement to the dispatcher")
        self.assertGreater(decision.confidence, 0)
        self.assertTrue(decision.reason)

    def test_executor_directed_task_routes_to_executor(self) -> None:
        decision = dispatcher.decide_dispatch(
            "Implement the scoped dispatcher patch",
            dispatcher.WORKERS,
        )

        self.assertEqual(decision.role, "executor")
        self.assertEqual(decision.next_input, "Implement the scoped dispatcher patch")
        self.assertIn("executor", decision.reason)

    def test_reviewer_directed_task_routes_to_reviewer(self) -> None:
        decision = dispatcher.decide_dispatch(
            "Review the dispatcher diff for regressions",
            dispatcher.WORKERS,
        )

        self.assertEqual(decision.role, "reviewer")
        self.assertEqual(decision.next_input, "Review the dispatcher diff for regressions")
        self.assertIn("reviewer", decision.reason)

    def test_planner_marker_takes_priority_over_executor_marker(self) -> None:
        decision = dispatcher.decide_dispatch(
            "Plan the fix for dispatcher routing",
            dispatcher.WORKERS,
        )

        self.assertEqual(decision.role, "planner")

    def test_orchestrator_plan_chat_command_forces_planner(self) -> None:
        decision = dispatcher.decide_dispatch(
            "оркестратор план Сделай калькулятор",
            dispatcher.WORKERS,
        )

        self.assertEqual(decision.role, "planner")
        self.assertEqual(decision.next_input, "Сделай калькулятор")
        self.assertIn("forced planner", decision.reason)

    def test_orchestrator_chat_command_uses_default_routing(self) -> None:
        decision = dispatcher.decide_dispatch(
            "оркестратор Сделай мне калькулятор",
            dispatcher.WORKERS,
        )

        self.assertEqual(decision.role, "executor")
        self.assertEqual(decision.next_input, "Сделай мне калькулятор")
        self.assertIn("executor", decision.reason)

    def test_ambiguous_task_falls_back_to_planner_and_runs_one_worker(self) -> None:
        original_runs_dir = dispatcher.RUNS_DIR
        with tempfile.TemporaryDirectory() as temp_dir:
            dispatcher.RUNS_DIR = Path(temp_dir)
            try:
                log_path, outputs, decision = dispatcher.run_pipeline(
                    task="hello",
                    dry=True,
                    workers=dispatcher.WORKERS,
                    codex_command=None,
                    request_timeout_seconds=1,
                    turn_timeout_seconds=1,
                    use_worker_models=False,
                )
            finally:
                dispatcher.RUNS_DIR = original_runs_dir

            self.assertEqual(decision.role, "planner")
            self.assertNotEqual(decision.role, "executor")
            self.assertEqual(list(outputs), ["planner"])

            events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            decision_events = [event for event in events if event["type"] == "dispatch_decision"]
            self.assertEqual(len(decision_events), 1)
            self.assertEqual(decision_events[0]["role"], "planner")
            self.assertTrue(decision_events[0]["reason"])

    def test_chain_dry_run_runs_planner_executor_reviewer(self) -> None:
        original_runs_dir = dispatcher.RUNS_DIR
        with tempfile.TemporaryDirectory() as temp_dir:
            dispatcher.RUNS_DIR = Path(temp_dir)
            try:
                log_path, outputs, decision = dispatcher.run_pipeline(
                    task="оркестратор план Сделай калькулятор",
                    dry=True,
                    workers=dispatcher.WORKERS,
                    codex_command=None,
                    request_timeout_seconds=1,
                    turn_timeout_seconds=1,
                    use_worker_models=False,
                    chain=True,
                )
            finally:
                dispatcher.RUNS_DIR = original_runs_dir

            self.assertEqual(decision.role, "planner")
            self.assertEqual(list(outputs), ["planner", "executor", "reviewer"])

            events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            handoff_events = [event for event in events if event["type"] == "handoff"]
            self.assertEqual([event["to"] for event in handoff_events], ["planner", "executor", "reviewer"])
            final_events = [event for event in events if event["type"] == "final"]
            self.assertEqual(len(final_events), 1)
            self.assertTrue(final_events[0]["chain"])

    def test_plan_only_returns_approval_plan_without_creating_project(self) -> None:
        original_runs_dir = dispatcher.RUNS_DIR
        with tempfile.TemporaryDirectory() as temp_dir:
            dispatcher.RUNS_DIR = Path(temp_dir) / "runs"
            FakeCodexAppServer.prompts = []
            try:
                with patch.object(dispatcher, "CodexAppServer", FakeCodexAppServer):
                    log_path, outputs, decision = dispatcher.run_pipeline(
                        task="orchestrator plan Make a calculator",
                        dry=False,
                        workers=dispatcher.WORKERS,
                        codex_command=None,
                        request_timeout_seconds=1,
                        turn_timeout_seconds=1,
                        use_worker_models=False,
                        plan_only=True,
                    )
            finally:
                dispatcher.RUNS_DIR = original_runs_dir

            self.assertEqual(decision.role, "planner")
            self.assertEqual(list(outputs), ["planner"])
            self.assertIn("agent output from planner", outputs["planner"])
            self.assertIn("Make a calculator", outputs["planner"])
            self.assertEqual(len(FakeCodexAppServer.prompts), 1)
            self.assertIn("Do not reuse a generic template", FakeCodexAppServer.prompts[0])
            self.assertIn(".mini_orchestrator/test-runs/<task-slug>/<version>/", FakeCodexAppServer.prompts[0])
            self.assertFalse((Path(temp_dir) / "test-projects" / "calculator").exists())

            events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            final_events = [event for event in events if event["type"] == "final"]
            self.assertEqual(len(final_events), 1)
            self.assertTrue(final_events[0]["planOnly"])

    def test_plan_only_dry_run_returns_generic_plan_for_non_demo_task(self) -> None:
        original_runs_dir = dispatcher.RUNS_DIR
        with tempfile.TemporaryDirectory() as temp_dir:
            dispatcher.RUNS_DIR = Path(temp_dir) / "runs"
            try:
                log_path, outputs, decision = dispatcher.run_pipeline(
                    task="orchestrator plan Build an AI agent for a marketplace",
                    dry=True,
                    workers=dispatcher.WORKERS,
                    codex_command=None,
                    request_timeout_seconds=1,
                    turn_timeout_seconds=1,
                    use_worker_models=False,
                    plan_only=True,
                )
            finally:
                dispatcher.RUNS_DIR = original_runs_dir

            self.assertEqual(decision.role, "planner")
            self.assertEqual(list(outputs), ["planner"])
            self.assertIn("Approval plan", outputs["planner"])
            self.assertIn("AI agent for a marketplace", outputs["planner"])
            self.assertNotIn("local demo project", outputs["planner"])
            self.assertTrue(log_path.exists())

    def test_plan_only_sends_ui_request_to_planner_agent(self) -> None:
        original_runs_dir = dispatcher.RUNS_DIR
        with tempfile.TemporaryDirectory() as temp_dir:
            dispatcher.RUNS_DIR = Path(temp_dir) / "runs"
            FakeCodexAppServer.prompts = []
            try:
                with patch.object(dispatcher, "CodexAppServer", FakeCodexAppServer):
                    _, outputs, _ = dispatcher.run_pipeline(
                        task="orchestrator plan Make a calculator and describe the UI",
                        dry=False,
                        workers=dispatcher.WORKERS,
                        codex_command=None,
                        request_timeout_seconds=1,
                        turn_timeout_seconds=1,
                        use_worker_models=False,
                        plan_only=True,
                    )
            finally:
                dispatcher.RUNS_DIR = original_runs_dir

            self.assertIn("agent output from planner", outputs["planner"])
            self.assertEqual(len(FakeCodexAppServer.prompts), 1)
            self.assertIn("key UI/UX notes", FakeCodexAppServer.prompts[0])
            self.assertIn("Make a calculator and describe the UI", FakeCodexAppServer.prompts[0])
            self.assertNotIn("Python CLI calculator", outputs["planner"])

    def test_release_chain_runs_planner_executor_reviewer_through_codex_server(self) -> None:
        original_runs_dir = dispatcher.RUNS_DIR
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            dispatcher.RUNS_DIR = temp_path / "runs"
            FakeCodexAppServer.prompts = []
            try:
                with patch.object(dispatcher, "CodexAppServer", FakeCodexAppServer):
                    log_path, outputs, decision = dispatcher.run_pipeline(
                        task="orchestrator plan Make a release workflow",
                        dry=False,
                        workers=dispatcher.WORKERS,
                        codex_command=None,
                        request_timeout_seconds=1,
                        turn_timeout_seconds=1,
                        use_worker_models=False,
                        chain=True,
                    )
            finally:
                dispatcher.RUNS_DIR = original_runs_dir

            self.assertEqual(decision.role, "planner")
            self.assertEqual(list(outputs), ["planner", "executor", "reviewer"])
            self.assertEqual(len(FakeCodexAppServer.prompts), 3)
            self.assertIn("Make a release workflow", FakeCodexAppServer.prompts[0])
            self.assertIn("planner output", FakeCodexAppServer.prompts[1])
            self.assertIn("executor output", FakeCodexAppServer.prompts[2])
            self.assertTrue(all(".mini_orchestrator/test-runs/<task-slug>/<version>/" in prompt for prompt in FakeCodexAppServer.prompts))
            self.assertTrue(all("launch-desk" in prompt for prompt in FakeCodexAppServer.prompts))

            events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            final_events = [event for event in events if event["type"] == "final"]
            self.assertEqual(len(final_events), 1)
            self.assertTrue(final_events[0]["chain"])
            self.assertNotIn("localTestProject", final_events[0])

    def test_chain_preset_file_controls_worker_models_and_order(self) -> None:
        original_runs_dir = dispatcher.RUNS_DIR
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            dispatcher.RUNS_DIR = temp_path / "runs"
            preset_path = temp_path / "chain.json"
            preset_path.write_text(
                json.dumps(
                    {
                        "id": "custom-chain",
                        "name": "Custom chain",
                        "flow": {
                            "agents": [
                                {
                                    "id": "planner-card",
                                    "name": "Planner",
                                    "role": "Planner",
                                    "preset": "planner",
                                    "llm": "gpt-5.5",
                                    "reasoning": "high",
                                    "accessMode": "read-only",
                                    "workPackage": {
                                        "instructions": "Plan only.",
                                        "currentObjective": "Plan the work.",
                                        "inputsArtifacts": "Task.",
                                        "constraints": "Read only.",
                                        "previousOutputs": "None.",
                                        "allowedTools": "Inspect.",
                                        "expectedOutput": "Plan.",
                                    },
                                },
                                {
                                    "id": "executor-card",
                                    "name": "Spark Executor",
                                    "role": "Executor",
                                    "preset": "executor",
                                    "llm": "gpt-5.3-codex-spark",
                                    "reasoning": "medium",
                                    "accessMode": "workspace-write",
                                    "workPackage": {
                                        "instructions": "Execute with Spark.",
                                        "currentObjective": "Implement the work.",
                                        "inputsArtifacts": "Plan.",
                                        "constraints": "Scoped edits.",
                                        "previousOutputs": "Planner output.",
                                        "allowedTools": "Edit and test.",
                                        "expectedOutput": "Implementation summary.",
                                    },
                                },
                            ],
                            "connections": [
                                {
                                    "fromAgentId": "planner-card",
                                    "toAgentId": "executor-card",
                                    "fromPort": "success",
                                }
                            ],
                        },
                    }
                ),
                encoding="utf-8",
            )
            try:
                workers = dispatcher.workers_from_chain_preset_file(preset_path, temp_path)
                log_path, outputs, _ = dispatcher.run_pipeline(
                    task="orchestrator plan Use selected chain",
                    dry=True,
                    workers=workers,
                    codex_command=None,
                    request_timeout_seconds=1,
                    turn_timeout_seconds=1,
                    use_worker_models=False,
                    chain=True,
                )
            finally:
                dispatcher.RUNS_DIR = original_runs_dir

            self.assertEqual([worker.name for worker in workers], ["planner", "executor"])
            self.assertEqual([worker.model for worker in workers], ["gpt-5.5", "gpt-5.3-codex-spark"])
            self.assertEqual(list(outputs), ["planner", "executor"])
            events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            started_events = [event for event in events if event["type"] == "agent_started"]
            self.assertEqual([event["model"] for event in started_events], ["gpt-5.5", "gpt-5.3-codex-spark"])

    def test_chain_preset_agents_require_explicit_models(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            preset_path = temp_path / "legacy-chain.json"
            preset_path.write_text(
                json.dumps(
                    {
                        "id": "legacy-chain",
                        "name": "Legacy chain",
                        "flow": {
                            "agents": [
                                {
                                    "id": "reviewer-card",
                                    "name": "Reviewer",
                                    "role": "Reviewer",
                                    "preset": "reviewer",
                                }
                            ],
                            "connections": [],
                        },
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "Agent model is required"):
                dispatcher.workers_from_chain_preset_file(preset_path, temp_path)

    def test_chain_preset_workers_follow_pm_control_graph_order(self) -> None:
        def agent(agent_id: str, name: str, role: str) -> dict[str, object]:
            return {
                "id": agent_id,
                "name": name,
                "role": role,
                "preset": role.lower(),
                "llm": "gpt-5.5",
                "reasoning": "medium",
                "accessMode": "workspace-write",
                "workPackage": {
                    "instructions": f"Act as {role}.",
                    "currentObjective": "Complete the assigned step.",
                    "inputsArtifacts": "Task and previous outputs.",
                    "constraints": "Stay in scope.",
                    "previousOutputs": "Use prior outputs.",
                    "allowedTools": "Use approved tools.",
                    "expectedOutput": "Structured result.",
                },
            }

        preset = {
            "id": "pm-chain",
            "name": "PM chain",
            "updatedAt": "2026-06-24T00:00:00Z",
            "flow": {
                "agents": [
                    agent("executor", "Executor", "Executor"),
                    agent("reviewer", "Reviewer", "Reviewer"),
                    agent("qa", "QA", "QA"),
                    agent("pm", "PM", "PM"),
                    agent("planner", "Planner", "Planner"),
                ],
                "connections": [
                    {"fromAgentId": "executor", "toAgentId": "qa", "fromPort": "success"},
                    {"fromAgentId": "qa", "toAgentId": "executor", "fromPort": "failure"},
                    {"fromAgentId": "planner", "toAgentId": "pm", "fromPort": "success"},
                    {"fromAgentId": "pm", "toAgentId": "executor", "fromPort": "failure"},
                    {"fromAgentId": "qa", "toAgentId": "pm", "fromPort": "success"},
                    {"fromAgentId": "pm", "toAgentId": "reviewer", "fromPort": "success"},
                ],
            },
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            preset_path = temp_path / "pm-chain.json"
            preset_path.write_text(json.dumps(preset), encoding="utf-8")
            workers = dispatcher.workers_from_chain_preset_file(preset_path, temp_path)

        self.assertEqual([worker.source_agent_id for worker in workers], ["planner", "pm", "executor", "qa", "reviewer"])


if __name__ == "__main__":
    unittest.main()
