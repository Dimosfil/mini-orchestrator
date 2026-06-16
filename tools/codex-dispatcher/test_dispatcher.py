from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import dispatcher


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


if __name__ == "__main__":
    unittest.main()
