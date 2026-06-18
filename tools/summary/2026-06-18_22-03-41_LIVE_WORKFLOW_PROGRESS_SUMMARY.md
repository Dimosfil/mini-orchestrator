# Handoff Summary: Live workflow progress and calculator smoke

Date: 2026-06-18 22:03:41
Thread topic: Make the mini-orchestrator UI show an end-to-end dispatcher
workflow lifecycle, using the calculator task as a recurring smoke test.

## Product Direction

- User confirmed the current left-side command block should stay for now.
- The desired architecture remains:
  - LaunchDesk holds global tasks.
  - WorkNest structures/routes work items.
  - mini-orchestrator shows how a routed workflow executes.
- The immediate goal was not to improve the calculator itself, but to make the
  orchestrator UI visibly show workflow dynamics.

## Implemented

- Added dispatcher live-run replay:
  - `mini_orchestrator/live_runs.py`
  - Reads `tools/codex-dispatcher/runs/*.jsonl`.
  - Produces run cards with status, current agent, mode, thread ids, tokens,
    approval state, event counts, and outputs.
- Switched `/api/daemon/runs` from demo-only data to live dispatcher JSONL state:
  - `mini_orchestrator/ui.py`
- Added background dispatcher workflow start:
  - `/api/dispatcher/run` accepts `background=true`.
  - UI receives a stable `runId` immediately and can poll live state.
  - Background stdout/stderr go under `.mini_orchestrator/dispatcher-processes/`.
- Fixed Russian task transport from UI:
  - UI dispatcher requests now write task text to UTF-8 files under
    `.mini_orchestrator/dispatcher-tasks/`.
  - Dispatcher is invoked with `--task-file` instead of raw `--task`.
- Added stable dispatcher log naming:
  - `tools/codex-dispatcher/cli.py` accepts `--run-id`.
  - `tools/codex-dispatcher/pipeline.py` uses `<run-id>.jsonl`.
- Improved terminal error evidence:
  - Pipeline writes `error` events before re-raising planner/executor/reviewer
    turn failures.
- Updated UI:
  - `mini_orchestrator/web/index.html`
  - Workflow button starts background mode.
  - Live Runs polls every 3 seconds.
  - Run cards show `Mode`, `Approval`, current agent, and `waiting_approval`.
- Updated docs/memory:
  - `tools/codex-dispatcher/EVENT_PROTOCOL.md`
  - `tools/project-memory/pending-tasks.md`
  - `/agent/contract` now documents `background` and live dispatcher run mode.
- Added tests:
  - `tests/test_live_runs.py`

## Calculator Smoke Evidence

- Disposable calculator artifact remains under:
  - `.mini_orchestrator/test-runs/calculator-demo/index.html`
  - `.mini_orchestrator/test-runs/calculator-demo/README.md`
- UTF-8 Russian plan smoke:
  - Task: `оркестратор план Сделай калькулятор`
  - Run id/log: `smoke-russian-task`
  - Result: planner saw `Сделай калькулятор`, not `????????`.
- Background dry-run calculator chain:
  - Run id: `ui-1cbfb5f44adb`
  - Result: `done`
  - Outputs included planner, executor, reviewer dry-run messages.
- Real read-only calculator inspection chain:
  - Run id: `ui-3354f9fc90c0`
  - Polling showed:
    - `queued`
    - `running / planner`
    - `running / executor`
    - `running / reviewer`
    - `done / reviewer / Workflow completed`
  - Reviewer result: no findings; validation was static, not browser-executed.

## Approval Gate Finding

- A real file-writing calculator chain reached executor and then stopped on
  Codex file-change approval.
- Old behavior: parent API timed out after waiting for the worker turn.
- New behavior: live replay surfaces the same condition as `waiting_approval`
  with `approval.required=true`.
- Next useful product step: decide how the mini-orchestrator UI should handle
  Codex file-change approvals:
  - show a clear "approve in worker thread" instruction, or
  - add a first-class approval bridge if the app-server protocol supports it.

## Verification

- `python -m compileall mini_orchestrator tools\codex-dispatcher`
- `python -m pytest`
  - 33 tests passed.
- `git diff --check` passed for scoped changed files.
- UI was restarted at:
  - `http://127.0.0.1:8000/`
- Health check passed:
  - `GET /health` -> `{"status":"ok"}`
- Contract check confirmed:
  - `/api/dispatcher/run` required `task`, `approved`
  - optional `background`, `mode`

## Current Worktree Notes

- Scoped changes from this thread include:
  - `mini_orchestrator/ui.py`
  - `mini_orchestrator/web/index.html`
  - `mini_orchestrator/live_runs.py`
  - `tests/test_live_runs.py`
  - `tools/codex-dispatcher/cli.py`
  - `tools/codex-dispatcher/pipeline.py`
  - `tools/codex-dispatcher/EVENT_PROTOCOL.md`
  - `tools/project-memory/pending-tasks.md`
- There were pre-existing/unrelated dirty project-memory and summary files:
  - `tools/project-memory/git-preferences.json`
  - `tools/project-memory/system-preferences.json`
  - `tools/project-memory/specs/integration-contracts/connected-projects.md`
  - older untracked summary files from the Symphony orientation work.

## Next Useful Context

- The UI now demonstrates live workflow dynamics for background runs.
- For file-writing real workflows, `waiting_approval` is visible but not yet
  actionable from the mini-orchestrator UI.
- The calculator task is the current canonical smoke task for:
  - Russian task transport,
  - background dispatcher chain,
  - planner/executor/reviewer progression,
  - live run-state replay,
  - approval-gate visibility.
