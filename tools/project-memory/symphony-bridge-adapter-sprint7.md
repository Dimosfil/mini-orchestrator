# Symphony Bridge Adapter Sprint7

Date: 2026-06-19

## Purpose

This document records the accepted runtime workflow for the WorkNest sprint
`2026-06-19_17-01-10_symphony-bridge-adapter-sprint`.

Mini Orchestrator can read and display Symphony daemon state, but it must not
invent a Symphony task-intake protocol. Until Symphony exposes a documented
agent-facing intake endpoint through config-service, Mini Orchestrator treats
Symphony task-run submission as a blocker.

## Runtime Sources

Live Runs has three source modes:

- `dispatcher`: local daemon dry-run state plus dispatcher JSONL replay.
- `symphony`: read-only Symphony daemon state resolved from the `symphony`
  service record in GI config-service. `MINI_ORCHESTRATOR_DAEMON_STATE_URL`
  remains an explicit manual override for the state endpoint, and
  `MINI_ORCHESTRATOR_SYMPHONY_SERVICE_ID` can select a different service id.
- `combined`: dispatcher/local state plus Symphony state.

Combined mode is the default. Symphony errors or empty state do not hide
dispatcher runs. The UI shows a non-terminal Symphony unavailable note while
keeping dispatcher cards visible.

Every run state should expose the same base fields:

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

Dispatcher JSONL runs also include `eventTypes`, `approval`, `chainPreset`, and
`outputs` when available. Local daemon manifest dry-runs may include
`nodeStates`, `flowArtifacts`, and `reviewerVerdict`.

## Stale Dispatcher Runs

Dispatcher JSONL runs in active statuses are marked `stale` when:

- the recorded dispatcher process id is no longer running; or
- the log has not updated past
  `MINI_ORCHESTRATOR_DISPATCHER_STALE_AFTER_SECONDS`.

The default freshness window is 15 minutes. Stale runs move out of active counts
and into Human Review in the dashboard, with the stale reason visible on the
card.

## Symphony Intake Blocker

`POST /api/symphony/runs` validates approved task-run payloads and returns:

- `status: blocked`
- `code: symphony-intake-missing`
- `accepted: false`

The endpoint exists so UI and agents can call one stable local route, but the
route must not mutate Symphony until config-service resolves a Symphony record
with a documented external task-intake contract.

The future Symphony-side adapter should define:

- service id and config-service record;
- guide and contract endpoints;
- exact task-intake endpoint and payload schema;
- status mapping between Mini Orchestrator, WorkNest, and Symphony;
- idempotency key or duplicate-run handling;
- lifecycle ownership boundaries;
- health and failure reporting;
- no fallback-port behavior.

Supported Symphony bridge operations before task intake exists:

- `GET /api/v1/state` through `/api/daemon/runs?source=symphony`.
- `POST /api/v1/refresh` through `/api/symphony/refresh`.
- `GET /api/v1/{issue_identifier}` through
  `/api/symphony/issues/{issueIdentifier}`.

These are observability/control operations only. They do not create external
task runs and do not replace the missing task-intake contract.

## WorkNest Lifecycle

WorkNest remains the source of sprint tasks and the terminal completion sink.
Mini Orchestrator owns approval, visible chain execution, and Human Review.

Rules:

- Claim only through documented `next-task`.
- Complete only through documented `task-completed`.
- `done` completion requires explicit user acceptance (`ToDone`,
  `reviewDecision=done`, or `accepted=true`).
- Rejected work stays in Human Review or rework and is not final Done.
- Blocked completion is allowed only for unrecoverable blocked results.

## Smoke Commands

```powershell
python -m compileall mini_orchestrator tools\codex-dispatcher
python -m pytest tests
python tools\codex-dispatcher\dispatcher.py --task "orchestrator plan Smoke sprint7" --chain --dry-run
```

Optional live checks when services are running:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/daemon/runs?source=combined"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/daemon/runs?source=dispatcher"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/daemon/runs?source=symphony"
```
