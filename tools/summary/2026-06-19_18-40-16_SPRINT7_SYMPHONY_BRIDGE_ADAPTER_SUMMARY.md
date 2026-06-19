# Handoff Summary: Sprint7 Symphony Bridge Adapter

Date: 2026-06-19 18:40:16
Thread topic: WorkNest sprint7 execution, Live Runs source modes, Symphony bridge blocker, and UI/API verification

## User Intent

The user asked to start and then execute the whole WorkNest sprint shown in the
GI manager. The sprint is the WorkNest sprint with full id:

`2026-06-19_17-01-10_symphony-bridge-adapter-sprint`

The UI alias `sprint7` is not accepted by WorkNest API endpoints; manager API
calls require the full sprint id.

## WorkNest Sprint State

The first claimed task was:

- Order: `001`
- Title: `Переключение источника / Source switch`
- Task id:
  `mini-orchestrator:2026-06-19_17-01-10_symphony-bridge-adapter-sprint:001:source-switch-add-live-runs-source-modes-dispatcher-symphony-and-combined-so-an`
- WorkNest status after claim: `in_progress`
- StartedAt from WorkNest: `2026-06-19T15:03:39.042Z`

The code and documentation work for the whole sprint was completed locally, but
WorkNest tasks were not moved to terminal `done` because project rules require
explicit user acceptance (`ToDone`) before final Done. The WorkNest readback
still showed task `001` as `in_progress` and tasks `002`-`008` as `todo`.

## Implemented Runtime Behavior

Live Runs now has explicit source modes:

- `combined`: default; combines dispatcher/local runs with read-only Symphony
  state.
- `dispatcher`: local daemon dry-runs plus dispatcher JSONL replay only.
- `symphony`: read-only Symphony state only.

Combined mode must never hide dispatcher-chain runs when Symphony is empty,
disabled, unavailable, or timing out. Source badges are rendered in the UI for
`Dispatcher` and `Symphony`.

Dispatcher, local daemon, and Symphony run states now share a normalized base
shape including:

- `schemaVersion`
- `runId`
- `sourceKey`
- `sourceLabel`
- `status`
- `currentAgent`
- `task`
- `thread`
- `tokens`
- `artifacts`
- `stages`
- `createdAt`
- `updatedAt`
- `stale`

Dispatcher JSONL replay reads up to 50,000 lines so long real app-server logs
still expose terminal `final` events. This fixed the real sprint7 chain log
`tools/codex-dispatcher/runs/20260619-180339-f649b628.jsonl`, which now appears
as `done` in the live dashboard rather than a false active/stale run.

## Stale Detection

Old incomplete dispatcher JSONL runs are marked `stale` when an active-looking
run has no fresh event within
`MINI_ORCHESTRATOR_DISPATCHER_STALE_AFTER_SECONDS` or the recorded dispatcher
process is gone.

Default stale threshold: 15 minutes.

Stale runs leave active counts and are shown as review-worthy cards rather than
ongoing work.

## Symphony Bridge

Current Symphony config-service record still lacks a documented GI-style
guide/contract and task-intake endpoint. The registered Symphony service has
only `api/v1/state` as availability/temporary contract, and the process was not
reachable at `http://127.0.0.1:4000/api/v1/state` during this thread.

Therefore Mini Orchestrator must not invent or guess a Symphony intake payload.

`POST /api/symphony/runs` was added as a controlled blocker endpoint:

- It validates approved task-run payloads.
- It returns HTTP `200`, not `501`, so UI/chains can handle it as a normal
  controlled result.
- Payload includes:
  - `status: blocked`
  - `accepted: false`
  - `code: symphony-intake-missing`

This was changed after the user objected that HTTP `501` was not acceptable.

## WorkNest Lifecycle

WorkNest remains the task source and terminal completion sink.

Rules implemented/preserved:

- Claim only through documented WorkNest `next-task`.
- Complete only through documented WorkNest `task-completed`.
- Local `/api/worknest/complete` permits terminal `done` only with explicit
  user acceptance: `reviewDecision=done` or `accepted=true`.
- Rework/rejected tasks stay in Human Review or rework and are not final Done.

## Documentation And Memory

Updated durable memory:

- `tools/project-memory/pending-tasks.md`
- `tools/project-memory/symphony-bridge-adapter-sprint7.md`

Updated README:

- Live Runs source modes and precedence.
- Stale dispatcher run behavior.
- `/api/symphony/runs` blocker endpoint.
- WorkNest terminal completion acceptance gate.
- Current smoke/check commands.

## Verification

Final checks run successfully:

```powershell
python -m compileall mini_orchestrator tools\codex-dispatcher
python -m pytest tests
python tools\codex-dispatcher\dispatcher.py --task "orchestrator plan Smoke sprint7" --chain --dry-run
```

Final full test result after the `/api/symphony/runs` HTTP-status fix:

`71 passed`

Live UI was restarted and verified at:

`http://127.0.0.1:8000/`

Live HTTP checks:

- `GET /health` returned `{"status":"ok"}`.
- `GET /api/daemon/runs?source=combined` returned `sourceMode=combined`.
- Combined readback after parser-limit fix showed:
  - `Done=8`
  - `Stale=0`
  - sprint7 real chain run `20260619-180339-f649b628` as `done`
  - last event `Workflow completed`
- `POST /api/symphony/runs` returned HTTP `200` with
  `code=symphony-intake-missing`.

## Current Process State

The Mini Orchestrator UI process was restarted after the latest code changes.
The listener on port `8000` was a Python process running:

`python -m mini_orchestrator --ui`

The most recent observed PID was `27328`, but verify current PID if needed.

## Important Caveats

- The working tree contains many pre-existing uncommitted changes from earlier
  sprint work. Do not assume every dirty file was changed in this last request.
- Do not mark the WorkNest sprint/tasks terminal Done without explicit user
  `ToDone` acceptance.
- Do not implement real Symphony task intake until Symphony exposes a documented
  config-service-resolved contract/capability.
- The Symphony service record currently uses `/api/v1/state` as a temporary
  contract placeholder, not as a real task-intake contract.
