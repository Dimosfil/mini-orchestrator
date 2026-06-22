# Symphony Bridge Adapter Sprint7

Date: 2026-06-19

## Purpose

This document records the accepted runtime workflow for the WorkNest sprint
`2026-06-19_17-01-10_symphony-bridge-adapter-sprint`.

Mini Orchestrator can read and display Symphony daemon state. It can also build
documented intake payloads from the selected Mini Orchestrator chain preset.
The accepted production ownership model is Mini-owned chain execution: Mini
submits one next-agent handoff at a time, waits for Symphony's retained result,
stores that result on the task card, then submits the next agent with previous
outputs as context. Submission is allowed only when the `symphony`
config-service record and its contract expose a task-intake endpoint. If the
endpoint is missing, Mini Orchestrator records a visible blocked gateway run
instead of pretending Symphony accepted the task.

As of 2026-06-20, the connected local Symphony workspace exposes the required
contract and intake endpoint:

- `GET /agent/contract`
- `POST /api/v1/intake`

The config-service `symphony` record points `endpoints.contract` at
`http://127.0.0.1:4000/agent/contract`. Mini Orchestrator resolves that
contract, discovers `taskIntake: /api/v1/intake`, and submits the selected
chain preset as `mini-orchestrator.symphony-intake.v1`.

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

Startup contract: starting or restarting Mini Orchestrator must also start or
verify Symphony through the `symphony` service record in GI config-service.
Check `endpoints.availability` such as `/api/v1/state`; if it is unavailable,
launch Symphony with the service record startup command and verify it before
calling the full dashboard startup complete. This keeps observability live, but
does not change the intake blocker below.

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

## Symphony Gateway And Task Intake

`POST /api/symphony/runs` validates approved task-run payloads and requires live
Symphony observability. In `orchestrationMode=mini-owned-chain` or
`waitForCompletion=true`, Mini converts the selected chain preset into a series
of one-agent handoffs, reads the config-service-resolved Symphony contract, and
posts each handoff to a documented intake endpoint when available:

- `endpoints.taskIntake`
- `endpoints.agentIntake`
- `endpoints.intake`

The Mini-owned handoff payload schema is:

- `schemaVersion: mini-orchestrator.symphony-intake.v1`
- `dispatchStrategy: mini-owned-single-agent-handoff`
- `task`: one shared task card for the whole user-visible work item
- `taskCard`: Mini-owned checklist/current item state
- `chainPreset`: selected preset id/name/raw payload
- `chainControl`: handoff index, total agents, current agent id, previous
  output count, and the policy that Symphony may start a new worker or reuse
  an IDLE one
- `agentTasks[]`: exactly one item for the current preset agent, carrying that
  agent's id/name/role/preset, Codex model/speed/reasoning/access mode, work
  package, translations, current checklist item, and previous outputs

The older compatibility payload schema is still supported for adapter
compatibility:

- `schemaVersion: mini-orchestrator.symphony-intake.v1`
- `dispatchStrategy: one-symphony-agent-per-preset-stage`
- `task`: one shared task card for the whole user-visible work item
- `chainPreset`: selected preset id/name/raw payload
- `agentTasks[]`: one item per configured preset agent, carrying that agent's
  id/name/role/preset, Codex model/speed/reasoning/access mode, work package,
  translations, and the agent-specific stage task derived from the shared card

If no intake endpoint is documented, the route records a local gateway run with:

- `status: blocked`
- `mode: symphony-gateway`
- `lastError: symphony-intake-missing`
- selected `chainPreset` and per-stage placeholders

The Symphony-side adapter contract should define:

- service id and config-service record;
- guide and contract endpoints;
- exact task-intake endpoint and payload schema;
- status mapping between Mini Orchestrator, WorkNest, and Symphony;
- idempotency key or duplicate-run handling;
- lifecycle ownership boundaries;
- health and failure reporting;
- no fallback-port behavior.

Current local Symphony behavior:

- `POST /api/v1/intake` validates `approved=true`,
  `schemaVersion=mini-orchestrator.symphony-intake.v1`, a shared `task`, and a
  non-empty `agentTasks[]` array.
- For Mini-owned handoffs, Mini sends one `agentTasks[]` item and therefore
  Symphony creates one synthetic issue for the current agent step. Mini polls
  that issue/result before sending the next agent.
- For compatibility preset payloads, Symphony creates one synthetic issue per
  `agentTasks[]` item.
- Each synthetic issue carries the Mini task card, the preset agent settings,
  Codex model/reasoning/access mode, and work package in issue metadata.
- Mini-origin synthetic issues skip the Linear `after_create` bootstrap hook so
  they do not clone Symphony itself into the task workspace.
- On Windows, Symphony launches Codex app-server through Node and the local
  npm Codex `codex.js` entrypoint instead of broken `bash.exe`, PowerShell, or
  direct `.cmd` execution.
- The local `WORKFLOW.md` uses `codex app-server -c
  shell_environment_policy.inherit=all`; the Mini preset payload supplies model
  and reasoning settings per agent.

Verified smoke on 2026-06-20:

- Mini `POST /api/symphony/runs` returned `status=queued` with
  `intakeSubmitted=true`.
- Symphony accepted
  `MO-sym-intake-smoke-20260620-h-1-smoke-reviewer`.
- Symphony log recorded `Codex session completed` and
  `External intake agent completed` for that synthetic issue.

Implemented on 2026-06-22:

- Added Mini-side `mini-owned-single-agent-handoff` payload construction.
- Added `SymphonyGateway.run_mini_owned_chain`, which submits a single current
  agent, waits for the retained Symphony result, stores the output, and then
  submits the next preset agent with previous outputs as context.
- Added `/api/symphony/runs` support for
  `orchestrationMode=mini-owned-chain` / `waitForCompletion=true`.
- Focused Mini tests cover handoff payload shape, sequential handoff order, and
  existing Symphony daemon/gateway compatibility behavior.

Supported Symphony bridge operations without task intake:

- `GET /api/v1/state` through `/api/daemon/runs?source=symphony`.
- `POST /api/v1/refresh` through `/api/symphony/refresh`.
- `GET /api/v1/{issue_identifier}` through
  `/api/symphony/issues/{issueIdentifier}`.

These observability/control operations do not create external task runs and do
not replace the task-intake contract.

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
