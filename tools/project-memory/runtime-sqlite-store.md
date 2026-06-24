# Runtime SQLite Store

Date: 2026-06-20

## Contract

`.mini_orchestrator/` is the project-local runtime area. It must contain only:

- `runtime.sqlite3` as the SQLite runtime database.
- `test-runs/` as the file artifact tree for generated runnable demos and
  inspectable task outputs.

All other runtime themes must be stored in SQLite instead of ad hoc files under
`.mini_orchestrator/`.

## Database Location

Runtime DB path:

```text
.mini_orchestrator/runtime.sqlite3
```

The file is ignored by git through the existing `.mini_orchestrator/` ignore
rule.

## Storage Themes

Primary structured tables:

- `agent_cards`
- `worker_profiles`
- `agent_flows`
- `agent_flow_manifests`
- `daemon_runs`
- `daemon_events`
- `symphony_runs`
- `dispatcher_tasks`
- `dispatcher_chain_presets`
- `dispatcher_process_outputs`

Generic imported file table:

- `runtime_files`

`runtime_files` preserves source path, theme, topic, file name, content type,
encoding, binary/text payload, size, mtime, sha256, and import time for migrated
legacy runtime files.

## File Exceptions

`test-runs/` remains file-based because generated runnable artifacts need
inspectable directories, entry points, README files, static assets, and repeated
version folders.

No other `.mini_orchestrator/<theme>/` folder should be created for normal
runtime writes. If a new runtime theme is added, add a table or structured JSON
document storage in `mini_orchestrator/runtime_store.py`.

## Pre-Test Cleanup

Before `gi test`, clear runtime database state, dispatcher JSONL run logs, local
logs, and generated runtime artifacts so stale cards, process output,
dispatcher task snapshots, generated demos, and Symphony gateway runs do not
pollute the fresh verification result:

```powershell
python tools\clear_runtime_task_state.py
```

The full `gi test` command should use:

```powershell
python tools\run_gi_test.py --task "<release/full-system test task>"
```

That runner performs the cleanup and then launches the workflow through the
saved dashboard `current_run_config`, including the selected chain preset,
execution mode, and Symphony worker mode. Direct dispatcher CLI runs are
diagnostic only and must not be treated as `gi test`.

The cleanup preserves saved reusable chain presets in `agent_chain_presets`,
current dashboard run config in `runtime_meta`, and the runtime schema metadata.
It clears all other runtime tables, including builder drafts/cards/manifests,
task/run tables, dispatcher snapshots, Symphony gateway runs, and imported
runtime files. It also removes generated
`tools/codex-dispatcher/runs/*.jsonl` Live Runs cards and all
`.mini_orchestrator/` files/directories except `runtime.sqlite3` and SQLite side
cars.

## Migration

Migration command:

```powershell
python tools\migrate_runtime_to_sqlite.py
```

Prune imported non-`test-runs` files after import:

```powershell
python tools\migrate_runtime_to_sqlite.py --prune-files
```

The migration is idempotent for typed JSON documents and daemon JSONL events.

## Current Implementation Map

- `mini_orchestrator/runtime_store.py` owns schema creation and SQLite helpers.
- `mini_orchestrator/agent_flows.py` stores flow drafts and compiled manifests
  in SQLite.
- `mini_orchestrator/agent_profiles.py` stores visual agent cards and worker
  profile snapshots in SQLite.
- `mini_orchestrator/daemon_runs.py` stores local daemon run state and events
  in SQLite.
- `mini_orchestrator/symphony_daemon.py` stores local Symphony gateway runs in
  SQLite.
- `mini_orchestrator/ui.py` stores dispatcher tasks, selected chain presets,
  and background process output in SQLite.
- `tools/codex-dispatcher/cli.py` supports `--chain-preset-id` for loading the
  selected chain preset from SQLite.
- `tools/codex-dispatcher/worker_profiles.py` keeps generated chain worker
  instructions in memory on the `Worker` object instead of writing markdown
  profiles under `.mini_orchestrator/`.

## Verification Evidence

After migration and prune on 2026-06-20:

- `.mini_orchestrator/` contained only `runtime.sqlite3` and `test-runs/`.
- Imported file count: 94.
- Skipped file count: 0.
- `python -m pytest tests tools\codex-dispatcher\test_dispatcher.py` passed.
- `python -m compileall mini_orchestrator tools\codex-dispatcher tools\migrate_runtime_to_sqlite.py` passed.
