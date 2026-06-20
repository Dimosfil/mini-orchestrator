# Handoff Summary: Symphony Gateway And Dashboard Placement

Date: 2026-06-20

## User Intent

The user wanted Mini Orchestrator to run the visible workflow from a task to
review, with the key link being an agent chain executor under Symphony-style
supervision.

The UI placement requirement was clarified:

- task cards belong in the upper Kanban board;
- Symphony daemon/observability cards belong in the lower large daemon panel;
- clicking the current agent or a chain stage should reveal the agent's work
  details and configuration.

## Symphony Contract Finding

`D:\AI\symphony\elixir` was inspected as the approved external reference
workspace. No files were edited there.

Current Symphony HTTP routes are defined in
`D:\AI\symphony\elixir\lib\symphony_elixir_web\router.ex`:

- `GET /api/v1/state`
- `POST /api/v1/refresh`
- `GET /api/v1/:issue_identifier`

There is no documented external task-intake endpoint. Therefore Mini
Orchestrator must not claim that upstream Symphony has accepted a task run yet.
The local bridge records a visible gateway run with `symphony-intake-missing`
until Symphony exposes a real intake contract.

## Implemented

Backend:

- `mini_orchestrator/symphony_daemon.py`
  - Added local Symphony gateway run storage under
    `.mini_orchestrator/symphony-runs/`.
  - Added `create_symphony_gateway_run(...)` to record approved Symphony run
    requests with the selected chain preset.
  - Added `build_local_symphony_gateway_runs(...)`.
  - Added a `symphony-daemon-summary` record built from real Symphony
    `/api/v1/state` data.
- `mini_orchestrator/ui.py`
  - `/api/symphony/runs` now requires live Symphony observability and returns a
    persisted `symphony-gateway` run record.
  - `/api/daemon/runs?source=symphony` combines real Symphony daemon state with
    local gateway records.
  - The service contract now advertises `symphony-run-gateway` instead of the
    older blocker-only capability.

Frontend:

- `mini_orchestrator/web/index.html`
  - Upper Kanban now filters out Symphony daemon summary/snapshot records.
  - Lower daemon panel now renders Symphony daemon cards.
  - Gateway task cards remain in the upper Kanban.
  - Current agent and chain stage chips are clickable and open focused agent
    details.
  - If the Live Runs source selector is set to `Symphony`, approved workflow
    submission routes to `/api/symphony/runs`; otherwise it uses the dispatcher.

Docs and memory:

- `README.md` explains the Symphony gateway behavior and upstream intake limit.
- `tools/project-memory/symphony-bridge-adapter-sprint7.md` records the updated
  gateway semantics.
- `tools/project-memory/pending-tasks.md` contains completed checklists for:
  - Symphony-governed chain dashboard pass;
  - task/daemon placement fix.

## Verification Evidence

Automated checks passed:

- `python -m compileall mini_orchestrator`
- `python -m pytest` -> `102 passed`
- `node --check` against the extracted dashboard script

Live checks passed after restarting Mini Orchestrator:

- Mini Orchestrator health: `GET http://127.0.0.1:8000/health` returned
  `{"status":"ok"}`.
- Symphony state: `GET http://127.0.0.1:4000/api/v1/state` returned an empty
  live daemon snapshot.
- Symphony gateway smoke created:
  `symphony-gateway-05bffe1993e3`.
- Dispatcher smoke created:
  `ui-bef5a1138f48`, visible with status `done` and current agent `reviewer`.
- Current split from `GET /api/daemon/runs?source=symphony`:
  - task runs: `symphony-gateway-05bffe1993e3`;
  - daemon runs: `symphony-daemon-summary`.

Runtime status at handoff:

- Mini Orchestrator UI is running at `http://127.0.0.1:8000/`.
- Current listening Mini Orchestrator process observed on port `8000` was PID
  `81348`.
- Symphony was running at `http://127.0.0.1:4000/api/v1/state`.

## Repository State

There are uncommitted changes. Current `git status --short` showed:

- modified: `README.md`
- modified: `mini_orchestrator/symphony_daemon.py`
- modified: `mini_orchestrator/ui.py`
- modified: `mini_orchestrator/web/agents-builder.html`
- modified: `mini_orchestrator/web/index.html`
- modified: `tests/test_agent_builder_ui.py`
- modified: `tests/test_symphony_daemon.py`
- modified: `tools/project-memory/pending-tasks.md`
- modified: `tools/project-memory/symphony-bridge-adapter-sprint7.md`
- untracked: `tools/summary/2026-06-20_SYMPHONY_CONFIG_SERVICE_BRIDGE_SUMMARY.md`

Note: `mini_orchestrator/web/agents-builder.html` was already part of the dirty
worktree when writing this summary. Do not assume it belongs solely to the final
task/daemon placement change without inspecting its diff.

## Next Useful Context

The next true Symphony integration step is upstream-side: add or discover a
documented task-intake contract for Symphony. It should be exposed through
config-service with guide/contract endpoints, payload schema, idempotency,
lifecycle ownership, status mapping, and failure reporting.

Until that exists, Mini Orchestrator's `/api/symphony/runs` is a truthful local
gateway: it records the selected chain and shows the intended task card, but it
does not mutate Symphony or claim that the upstream daemon accepted the task.
