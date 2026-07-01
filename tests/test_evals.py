from __future__ import annotations

import json
import sys

from mini_orchestrator import runtime_store
from mini_orchestrator.cli import run_from_args
from mini_orchestrator.evals import run_eval_suite, upsert_eval_suite


def test_eval_runner_passes_basic_software_artifact_checks(tmp_path) -> None:
    artifact = tmp_path / ".mini_orchestrator" / "test-runs" / "web-app-basic" / "todo-app"
    artifact.mkdir(parents=True)
    (artifact / "package.json").write_text('{"scripts":{"test":"echo ok"}}', encoding="utf-8")
    (artifact / "README.md").write_text("Todo app\nAdd item\nDelete item\n", encoding="utf-8")
    (artifact / "app.log").write_text("started cleanly\n", encoding="utf-8")
    (artifact / "artifactManifest.json").write_text(
        json.dumps({"name": "Todo App", "entrypoint": "index.html"}),
        encoding="utf-8",
    )

    suite = {
        "id": "web-app-basic",
        "name": "Basic web app acceptance",
        "cases": [
            {
                "id": "todo-app",
                "checks": [
                    {"id": "package-json", "type": "file_exists", "path": "package.json"},
                    {"id": "readme", "type": "file_contains", "path": "README.md", "contains": ["Add item", "Delete item"]},
                    {"id": "manifest", "type": "artifact_manifest_check", "requiredFields": ["name", "entrypoint"]},
                    {
                        "id": "python-command",
                        "type": "command",
                        "command": [sys.executable, "-c", "from pathlib import Path; assert Path('package.json').is_file()"],
                    },
                    {"id": "logs", "type": "log_scan", "path": "app.log", "failPatterns": ["traceback", "critical error"]},
                ],
            }
        ],
    }

    report = run_eval_suite(tmp_path, suite)
    stored_report = runtime_store.get_json_document(tmp_path, "eval_reports", report["runId"])
    stored_results = runtime_store.list_eval_results(tmp_path, report["runId"])

    assert report["status"] == "passed"
    assert report["summary"] == {"cases": 1, "checks": 5, "passed": 5, "failed": 0}
    assert stored_report is not None
    assert len(stored_results) == 5


def test_eval_runner_fails_missing_artifact_and_blocks_escaping_paths(tmp_path) -> None:
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    suite = {
        "id": "escape-suite",
        "name": "Escape Suite",
        "cases": [
            {
                "id": "escape-case",
                "artifactPath": "artifact",
                "checks": [{"id": "escape", "type": "file_exists", "path": "../secret.txt"}],
            }
        ],
    }

    report = run_eval_suite(tmp_path, suite)

    assert report["status"] == "failed"
    assert report["results"][0]["checkId"] == "escape"
    assert "escapes allowed root" in report["results"][0]["message"]


def test_eval_suite_storage_and_cli_run(tmp_path, capsys) -> None:
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    (artifact / "package.json").write_text("{}", encoding="utf-8")
    suite = {
        "id": "cli-suite",
        "name": "CLI Suite",
        "cases": [
            {
                "id": "cli-case",
                "artifactPath": "artifact",
                "checks": [{"id": "package-json", "type": "json_valid", "path": "package.json"}],
            }
        ],
    }
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(json.dumps(suite), encoding="utf-8")

    code = run_from_args(["eval", "run", "--workdir", str(tmp_path), "--suite", str(suite_path)])
    output = json.loads(capsys.readouterr().out)
    saved_suite = upsert_eval_suite(tmp_path, suite)

    assert code == 0
    assert output["status"] == "passed"
    assert saved_suite["id"] == "cli-suite"
    assert runtime_store.get_json_document(tmp_path, "eval_suites", "cli-suite") is not None
