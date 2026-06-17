from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mini_orchestrator.config import OrchestratorConfig
from mini_orchestrator.tools import ToolRuntime


class ToolRuntimeTests(unittest.TestCase):
    def runtime_for(self, root: Path) -> ToolRuntime:
        return ToolRuntime(
            OrchestratorConfig(
                workspace_root=root,
                allowed_roots=[root],
                command_output_limit=500,
                command_timeout_seconds=2,
            )
        )

    def test_search_excludes_generated_and_noise_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "src").mkdir()
            (root / "src" / "note.txt").write_text("needle", encoding="utf-8")
            (root / ".git").mkdir()
            (root / ".git" / "packed-refs").write_text("needle", encoding="utf-8")
            (root / "__pycache__").mkdir()
            (root / "__pycache__" / "x.pyc").write_text("needle", encoding="utf-8")
            (root / "package-lock.json").write_text("needle", encoding="utf-8")

            result = self.runtime_for(root).execute("search", {"query": "needle"})

            self.assertTrue(result.success)
            self.assertIn(str(root / "src" / "note.txt"), result.output)
            self.assertNotIn(".git", result.output)
            self.assertNotIn("__pycache__", result.output)
            self.assertNotIn("package-lock.json", result.output)

    def test_search_rejects_path_outside_allowed_root(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir, tempfile.TemporaryDirectory() as outside_dir:
            result = self.runtime_for(Path(root_dir)).execute(
                "search",
                {"query": "needle", "path": outside_dir},
            )

            self.assertFalse(result.success)
            self.assertEqual(result.error, "search path is outside allowed workspace roots")

    def test_run_command_blocks_destructive_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = self.runtime_for(Path(temp_dir)).execute(
                "run_command",
                {"command": "git reset --hard"},
            )

            self.assertFalse(result.success)
            self.assertIn("blocked potentially destructive command", result.error or "")

    def test_run_command_reports_empty_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = self.runtime_for(Path(temp_dir)).execute("run_command", {"command": ""})

            self.assertFalse(result.success)
            self.assertEqual(result.error, "empty command")

    def test_run_command_reports_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = ToolRuntime(
                OrchestratorConfig(
                    workspace_root=root,
                    allowed_roots=[root],
                    command_output_limit=500,
                    command_timeout_seconds=0.01,
                )
            )
            result = runtime.execute(
                "run_command",
                {"command": "python -c \"import time; time.sleep(1)\""},
            )

            self.assertFalse(result.success)
            self.assertIn("timed out", result.error or "")


if __name__ == "__main__":
    unittest.main()
