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
        return f"agent plan from {worker.name}: {prompt.split('User task:', 1)[1].strip().splitlines()[0]}"


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
            self.assertIn("agent plan from planner", outputs["planner"])
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

            self.assertIn("agent plan from planner", outputs["planner"])
            self.assertEqual(len(FakeCodexAppServer.prompts), 1)
            self.assertIn("key UI/UX notes", FakeCodexAppServer.prompts[0])
            self.assertIn("Make a calculator and describe the UI", FakeCodexAppServer.prompts[0])
            self.assertNotIn("Python CLI calculator", outputs["planner"])

    def test_local_test_project_chain_creates_calculator_and_runs_checks(self) -> None:
        original_runs_dir = dispatcher.RUNS_DIR
        original_root = dispatcher.ROOT
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            dispatcher.ROOT = temp_path
            dispatcher.RUNS_DIR = temp_path / "runs"
            test_projects_dir = temp_path / "test-projects"
            try:
                log_path, outputs, decision = dispatcher.run_pipeline(
                    task="orchestrator plan Make a calculator",
                    dry=False,
                    workers=dispatcher.WORKERS,
                    codex_command=None,
                    request_timeout_seconds=1,
                    turn_timeout_seconds=1,
                    use_worker_models=False,
                    chain=True,
                    local_test_project=True,
                    test_projects_dir=test_projects_dir,
                    max_review_iterations=3,
                )
            finally:
                dispatcher.RUNS_DIR = original_runs_dir
                dispatcher.ROOT = original_root

            project_path = test_projects_dir / "calculator"
            self.assertEqual(decision.role, "planner")
            self.assertEqual(list(outputs), ["planner", "executor", "reviewer"])
            self.assertTrue((project_path / "calculator.py").exists())
            self.assertTrue((project_path / "test_calculator.py").exists())
            self.assertIn("wrote files", outputs["executor"])
            self.assertIn("Unit tests", outputs["reviewer"])
            self.assertIn("Final passed", outputs["reviewer"])
            self.assertIn("Application launch smoke", outputs["reviewer"])
            self.assertIn("UI smoke", outputs["reviewer"])

            events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            final_events = [event for event in events if event["type"] == "final"]
            self.assertEqual(len(final_events), 1)
            self.assertTrue(final_events[0]["localTestProject"])

    def test_local_test_project_chain_creates_construction_crm_and_runs_checks(self) -> None:
        original_runs_dir = dispatcher.RUNS_DIR
        original_root = dispatcher.ROOT
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            dispatcher.ROOT = temp_path
            dispatcher.RUNS_DIR = temp_path / "runs"
            test_projects_dir = temp_path / "test-projects"
            try:
                log_path, outputs, decision = dispatcher.run_pipeline(
                    task="orchestrator plan Make a CRM for a construction store",
                    dry=False,
                    workers=dispatcher.WORKERS,
                    codex_command=None,
                    request_timeout_seconds=1,
                    turn_timeout_seconds=1,
                    use_worker_models=False,
                    chain=True,
                    local_test_project=True,
                    test_projects_dir=test_projects_dir,
                    max_review_iterations=3,
                )
            finally:
                dispatcher.RUNS_DIR = original_runs_dir
                dispatcher.ROOT = original_root

            project_path = test_projects_dir / "construction-crm"
            self.assertEqual(decision.role, "planner")
            self.assertEqual(list(outputs), ["planner", "executor", "reviewer"])
            self.assertTrue((project_path / "crm.py").exists())
            self.assertTrue((project_path / "test_crm.py").exists())
            self.assertTrue((project_path / "index.html").exists())
            self.assertTrue((project_path / "app.js").exists())
            self.assertTrue((project_path / "ui_smoke.py").exists())
            self.assertIn("construction-store CRM", outputs["planner"])
            self.assertIn("interactive manager workspace", outputs["planner"])
            self.assertIn("Unit tests", outputs["reviewer"])
            self.assertIn("smoke passed: ORD-1001 picking total 8170.00", outputs["reviewer"])
            self.assertIn("UI smoke", outputs["reviewer"])
            self.assertIn("ui smoke passed", outputs["reviewer"])
            self.assertIn("Final passed", outputs["reviewer"])

            events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            final_events = [event for event in events if event["type"] == "final"]
            self.assertEqual(len(final_events), 1)
            self.assertTrue(final_events[0]["localTestProject"])

    def test_construction_crm_ui_smoke_rejects_inert_buttons(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            dispatcher.write_construction_crm_project(project_path)
            (project_path / "index.html").write_text(
                "<!doctype html><html><body><button>Dashboard</button><script src=\"app.js\"></script></body></html>",
                encoding="utf-8",
            )
            (project_path / "app.js").write_text("", encoding="utf-8")

            result = dispatcher.run_command(
                [dispatcher.sys.executable, str(project_path / "ui_smoke.py")],
                cwd=project_path,
            )

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("button(s) have no data-view/data-action contract", result.stderr)


if __name__ == "__main__":
    unittest.main()
