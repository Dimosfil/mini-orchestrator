from __future__ import annotations

from mini_orchestrator import runtime_store


def test_clear_temporary_task_state_preserves_presets_and_builder_data(tmp_path) -> None:
    runtime_store.upsert_json_document(
        tmp_path,
        "agent_chain_presets",
        "custom-chain",
        {"id": "custom-chain", "name": "Custom Chain", "flow": {}, "createdAt": "2026-06-24T00:00:00Z"},
    )
    runtime_store.upsert_json_document(
        tmp_path,
        "agent_flows",
        "draft-flow",
        {
            "id": "draft-flow",
            "name": "Draft Flow",
            "version": 1,
            "validationStatus": "valid",
            "createdAt": "2026-06-24T00:00:00Z",
            "updatedAt": "2026-06-24T00:00:00Z",
        },
    )
    runtime_store.upsert_json_document(
        tmp_path,
        "agent_cards",
        "default-card",
        {"id": "default-card", "name": "Default Card"},
    )

    runtime_store.upsert_json_document(
        tmp_path,
        "daemon_runs",
        "run-1",
        {
            "runId": "run-1",
            "status": "running",
            "createdAt": "2026-06-24T00:00:00Z",
            "updatedAt": "2026-06-24T00:00:00Z",
        },
    )
    runtime_store.insert_daemon_event(tmp_path, "run-1", {"type": "started"})
    runtime_store.upsert_json_document(
        tmp_path,
        "symphony_runs",
        "symphony-1",
        {
            "runId": "symphony-1",
            "status": "queued",
            "createdAt": "2026-06-24T00:00:00Z",
            "updatedAt": "2026-06-24T00:00:00Z",
        },
    )
    runtime_store.store_dispatcher_task(tmp_path, "dispatcher-1", "test task")
    runtime_store.store_dispatcher_chain_preset(tmp_path, "dispatcher-1", {"id": "selected-chain"})
    runtime_store.store_dispatcher_process_output(tmp_path, "dispatcher-1", "stdout", "output")
    runtime_store.upsert_json_document(
        tmp_path,
        "eval_suites",
        "suite-1",
        {"id": "suite-1", "name": "Suite", "cases": [{"id": "case-1", "checks": [{"type": "file_exists", "path": "x"}]}]},
    )
    runtime_store.upsert_json_document(
        tmp_path,
        "eval_runs",
        "eval-1",
        {"runId": "eval-1", "suiteId": "suite-1", "caseId": "case-1", "status": "failed", "createdAt": "now", "updatedAt": "now"},
    )
    runtime_store.replace_eval_results(
        tmp_path,
        "eval-1",
        [{"checkId": "check-1", "type": "file_exists", "status": "failed"}],
    )
    runtime_store.upsert_json_document(
        tmp_path,
        "eval_artifacts",
        "artifact-1",
        {"artifactId": "artifact-1", "runId": "eval-1", "path": "artifact", "createdAt": "now", "updatedAt": "now"},
    )
    runtime_store.upsert_json_document(
        tmp_path,
        "eval_reports",
        "eval-1",
        {"reportId": "eval-1", "runId": "eval-1", "status": "failed", "createdAt": "now", "updatedAt": "now"},
    )

    deleted = runtime_store.clear_temporary_task_state(tmp_path)
    counts = runtime_store.table_counts(tmp_path)

    assert deleted == {
        "daemon_events": 1,
        "daemon_runs": 1,
        "symphony_runs": 1,
        "dispatcher_tasks": 1,
        "dispatcher_chain_presets": 1,
        "dispatcher_process_outputs": 1,
        "eval_runs": 1,
        "eval_results": 1,
        "eval_artifacts": 1,
        "eval_reports": 1,
        "migration_runs": 0,
        "runtime_files": 0,
        "agent_cards": 1,
        "worker_profiles": 0,
        "agent_flows": 1,
        "agent_flow_manifests": 0,
    }
    assert counts["agent_chain_presets"] == 1
    assert counts["agent_flows"] == 0
    assert counts["agent_cards"] == 0
    assert counts["daemon_events"] == 0
    assert counts["daemon_runs"] == 0
    assert counts["symphony_runs"] == 0
    assert counts["dispatcher_tasks"] == 0
    assert counts["dispatcher_chain_presets"] == 0
    assert counts["dispatcher_process_outputs"] == 0
    assert counts["eval_suites"] == 1
    assert counts["eval_runs"] == 0
    assert counts["eval_results"] == 0
    assert counts["eval_artifacts"] == 0
    assert counts["eval_reports"] == 0


def test_clear_dispatcher_run_logs_removes_only_jsonl_logs(tmp_path) -> None:
    runs_dir = tmp_path / "tools" / "codex-dispatcher" / "runs"
    runs_dir.mkdir(parents=True)
    (runs_dir / "run-1.jsonl").write_text("{}", encoding="utf-8")
    (runs_dir / "run-2.jsonl").write_text("{}", encoding="utf-8")
    (runs_dir / "keep.txt").write_text("keep", encoding="utf-8")

    deleted = runtime_store.clear_dispatcher_run_logs(tmp_path)

    assert deleted == {"jsonl_files": 2}
    assert not (runs_dir / "run-1.jsonl").exists()
    assert not (runs_dir / "run-2.jsonl").exists()
    assert (runs_dir / "keep.txt").exists()


def test_clear_runtime_files_removes_runtime_artifacts_but_keeps_database(tmp_path) -> None:
    runtime_dir = tmp_path / ".mini_orchestrator"
    runtime_dir.mkdir()
    (runtime_dir / "runtime.sqlite3").write_text("db", encoding="utf-8")
    (runtime_dir / "runtime.sqlite3-wal").write_text("wal", encoding="utf-8")
    (runtime_dir / "symphony.out.log").write_text("log", encoding="utf-8")
    nested = runtime_dir / "test-runs" / "artifact"
    nested.mkdir(parents=True)
    (nested / "README.md").write_text("artifact", encoding="utf-8")

    deleted = runtime_store.clear_runtime_files(tmp_path)

    assert deleted == {"files": 1, "directories": 1}
    assert (runtime_dir / "runtime.sqlite3").exists()
    assert (runtime_dir / "runtime.sqlite3-wal").exists()
    assert not (runtime_dir / "symphony.out.log").exists()
    assert not (runtime_dir / "test-runs").exists()


def test_current_run_config_is_preserved_by_gi_test_cleanup(tmp_path) -> None:
    config = runtime_store.set_current_run_config(
        tmp_path,
        {
            "chainPresetId": "test-chain-1",
            "executionMode": "symphony",
            "symphonyWorkerMode": "debug-new-worker",
        },
    )

    runtime_store.upsert_json_document(
        tmp_path,
        "symphony_runs",
        "run-1",
        {"runId": "run-1", "status": "queued", "createdAt": "now", "updatedAt": "now"},
    )
    runtime_store.clear_temporary_task_state(tmp_path)
    preserved = runtime_store.get_current_run_config(tmp_path)

    assert config["chainPresetId"] == "test-chain-1"
    assert preserved is not None
    assert preserved["chainPresetId"] == "test-chain-1"
    assert preserved["executionMode"] == "symphony"
    assert preserved["symphonyWorkerMode"] == "debug-new-worker"
