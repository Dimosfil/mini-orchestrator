from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import dispatcher


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

    def run_turn(self, thread_id: str, worker: dispatcher.Worker, prompt: str) -> str:
        self.prompts.append(prompt)
        if "User task:" in prompt:
            task = prompt.split("User task:", 1)[1].strip().splitlines()[0]
        else:
            task = prompt.split("Current task:", 1)[1].strip().splitlines()[0]
        return f"agent output from {worker.name}: {task}"


class DispatchDecisionTests(unittest.TestCase):
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

            events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            final_events = [event for event in events if event["type"] == "final"]
            self.assertEqual(len(final_events), 1)
            self.assertTrue(final_events[0]["chain"])
            self.assertNotIn("localTestProject", final_events[0])


if __name__ == "__main__":
    unittest.main()
