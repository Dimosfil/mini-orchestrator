# MVP Current State And Remaining Work

Date: 2026-06-19

## Purpose

This note consolidates what exists in the current mini-orchestrator workspace
and defines the remaining work for a reviewable MVP.

There are now two useful MVP layers:

1. Core orchestrator MVP: a package-native `plan -> execute -> validate` CLI
   loop for bounded local actions.
2. Product MVP: a web UI and dispatcher surface where a user can approve a
   task, run it through a visible agent chain, inspect progress, review the
   result, and eventually connect the lifecycle to WorkNest.

The core orchestrator MVP is implemented. The remaining work is mostly in the
product MVP around real compiled-flow execution, task lifecycle acceptance, and
release hardening.

## Current Implementation Inventory

### Runtime And Packaging

- Python package `mini_orchestrator` with console entry point
  `mini-orchestrator = mini_orchestrator.cli:run_from_args`.
- Install contract is recorded in `README.md`:
  `python -m pip install -e .`.
- UI startup is `python -m mini_orchestrator --ui`.
- Web UI startup must resolve the `mini-orchestrator` service record through GI
  config-service before binding a port.
- Full dashboard startup also requires Symphony availability. On Mini
  Orchestrator start or restart, resolve the `symphony` service through GI
  config-service, check its availability endpoint, and start it from the service
  record startup command if it is not already healthy. Treat unavailable
  Symphony as an incomplete startup for Live Runs Combined/Symphony views.
- `launch-desk/` is retained as legacy/experimental and is not part of the
  active runtime.

### Core Orchestrator

- `mini_orchestrator/models.py` defines the task/action state shape.
- `router.py`, `planner.py`, `executor.py`, `validator.py`, and
  `orchestrator.py` implement the bounded `plan -> execute -> validate` loop.
- `tools.py` implements the allowlisted local tool runtime:
  `read_file`, `search`, `apply_patch`, `run_command`, and direct `respond`.
- `command_adapter.py` blocks known dangerous command shapes before execution.
- JSONL event logging exists for replay/debug.
- `llm.py` and planner integration provide an optional OpenAI-compatible
  coordinator path with rule fallback when no API key is configured.

### Codex Dispatcher Path

- `tools/codex-dispatcher/` contains the release dispatcher modules:
  routing, prompts, event protocol, Codex app-server transport, pipeline, and
  CLI.
- Dispatcher supports:
  - single-worker planner/executor/reviewer routing;
  - `--plan-only` planner proposal mode;
  - approved chain-preset execution;
  - dry-run mode for parser/log smoke checks;
  - WorkNest task claim input through config-service-resolved manager records.
- `planner -> executor -> reviewer` is the default example chain, not a fixed
  workflow. A selected chain preset may contain any approved number of
  configured agents and stages.
- Local calculator/CRM demo generation was removed from the active release
  dispatcher surface.
- Dispatcher JSONL logs are consumed by Live Runs for visible progress.

### Web UI

- `mini_orchestrator/ui.py` serves the dashboard, Agent Builder, service guide,
  contract, and API endpoints.
- Main dashboard supports:
  - dispatcher plan preview;
  - approved dispatcher workflow runs;
  - confirmed execution mode selection between Dispatcher and Symphony;
  - chain preset selection;
  - core orchestrator run;
  - Live Runs/Kanban style state;
  - technical dispatcher summaries.
- `mini_orchestrator/web/index.html` is the active dashboard.
- `mini_orchestrator/web/agents-builder.html` is the visual card/chain builder.

### Visual Agents And Flow Contracts

- Visual agent cards have model, speed, reasoning, access mode, role, and
  work-package fields.
- Agent mini-chat uses the backend and the Codex app-server dispatcher path for
  live model checks; `rules` cards are rejected as non-LLM.
- Work-package translation is treated as UI helper behavior with a dedicated
  helper model/path.
- `agent_profiles.py` supports default selected card persistence, validation,
  profile compilation, and selected-card task prompt generation.
- `agent_flows.py` supports backend flow persistence, validation, and approved
  manifest compilation.
- Backend flow endpoints exist:
  - `GET/POST /api/agent-flows`
  - `GET/PUT /api/agent-flows/{id}`
  - `POST /api/agent-flows/{id}/validate`
  - `POST /api/agent-flows/{id}/compile`
- Compiled flow manifests are immutable snapshots under the generated
  `.mini_orchestrator/` runtime area.

### Daemon And Live Runs

- `daemon_runs.py` implements in-process dry-run daemon execution:
  - one-card manifest dry run;
  - linear multi-card manifest graph dry run;
  - replayable run state and JSONL events.
- Successful compiled-flow dry-runs now finish as local `review` runs. The
  dashboard records `ToDone`/`Доработки` through `/api/daemon/review`, which
  updates the generated run state before any optional WorkNest terminal
  completion.
- `live_runs.py` normalizes dispatcher event logs into planner/executor/reviewer
  stage state.
- `symphony_daemon.py` can read and normalize a configured Symphony daemon state
  endpoint, build a preset-based Symphony intake payload, and submit it only
  when the config-service-resolved Symphony contract exposes a documented intake
  endpoint.
- Symphony intake payloads use
  `schemaVersion=mini-orchestrator.symphony-intake.v1` and one `agentTasks[]`
  item per selected preset agent, carrying that agent's Codex model, reasoning,
  access mode, work package, translations, and shared task card.
- When Symphony intake is missing, the gateway records a visible blocked run
  instead of claiming the task was accepted.
- Dashboard Live Runs renders task cards, active stage state, node artifacts,
  reviewer verdicts, Human Review, and Done areas.

### WorkNest Bridge

- `worknest_bridge.py` resolves the configured WorkNest manager through
  config-service.
- The bridge reads the WorkNest contract before state-changing calls.
- Supported operations are deliberately narrow:
  - `next-task` claim;
  - terminal `task-completed` with `done` or `blocked`.
- No direct WorkNest storage reads, arbitrary task movement, or progress/workpad
  writes are implemented without a documented service capability.

### Tests

Current tests cover:

- core model/router/planner/executor/validator behavior;
- tool runtime and command guardrails;
- service discovery startup rules;
- dispatcher/live-run replay;
- visual agent API behavior;
- agent profile validation/compile;
- backend agent flow CRUD/validate/compile;
- daemon dry-run state and events;
- Symphony daemon state mapping;
- WorkNest lifecycle bridge contract gating;
- UI static invariants for dashboard and Agent Builder.

## Current MVP Cut Line

For the next reviewable product MVP, the practical target should be:

1. User opens the configured web UI.
2. User writes or selects a task.
3. User selects a saved/default agent chain preset.
4. User gets a planner proposal and explicitly approves it.
5. System starts one visible task card in Live Runs, not separate cards for
   every worker.
6. The card shows current agent/stage, stage output, blocker/failure state, and
   final reviewer verdict.
7. Finished agent work lands in Human Review.
8. User chooses `ToDone` to accept or `Доработки` to send it back for another
   pass.
9. If WorkNest is configured, only documented terminal completion/blocking is
   reported through its contract.
10. The whole path has a repeatable smoke test and a short operator runbook.

This cut line does not require a separate daemon service yet. It can continue
to use the current in-process daemon runner and dispatcher JSONL replay as long
as the UI is honest about whether a run is dry-run, dispatcher-backed, or
external-daemon-backed.

## Verification Snapshot

Run on 2026-06-19 during this consolidation pass:

- `python -m compileall mini_orchestrator tools\codex-dispatcher` passed.
- `python tools\codex-dispatcher\dispatcher.py --task "orchestrator plan Smoke MVP status" --chain --dry-run` passed.
- `python -m pytest tests` passed: 61 tests.

No live UI smoke was run in this pass because that requires the configured
config-service record and a running web process. The next UI-focused MVP pass
should verify startup and browser/API behavior through the documented
config-service path.

## Remaining Work To MVP

### P0: Make The Happy Path Coherent

- Add or confirm one dashboard workflow that runs an approved task through the
  selected saved chain preset without relying on browser-only state.
- Ensure the selected chain is either a backend-saved/compiled manifest or is
  explicitly labeled as a dispatcher-chain preset, not an executable saved flow.
- Make Human Review actions durable enough for the MVP:
  - `ToDone` records accepted completion in local run state;
  - `Доработки` records rework/needs-changes in local run state;
  - WorkNest completion is called only when a documented terminal operation is
    available and selected.
- Keep exactly one visual task card per executing chain and expose
  `currentAgent`/stage state inside that card.
- Add a single smoke script or documented command sequence for the full
  approve-run-review path.

### P0: Resolve Real vs Dry-Run Execution Boundaries

- Decide which execution mode is the MVP default:
  - real Codex app-server dispatcher chain; or
  - compiled-flow dry-run daemon runner; or
  - both, with clear labels and separate buttons.
- If real Codex app-server chain is the default, surface approval/model/tool
  blockers in Live Runs instead of letting the parent request time out.
- If compiled-flow daemon dry-run is the default, make the UI call the compiled
  manifest runner from the main dashboard, not only from Agent Builder internals.
- Record the selected default in README and project memory.

### P0: Verification Baseline

- Run the full Python test suite after the current uncommitted sprint changes.
- Run `python -m compileall mini_orchestrator tools\codex-dispatcher`.
- Run at least one dry-run dispatcher chain smoke.
- Run one UI/API smoke if config-service and the `mini-orchestrator` service
  record are available.
- Capture any environment blockers as MVP blockers, not as vague TODOs.

### P1: WorkNest Lifecycle MVP

- Keep WorkNest integration terminal-only unless the WorkNest contract adds
  progress/workpad capabilities.
- Add a clear UI state for "ready result waiting for user review" that is not
  automatically final Done.
- On `ToDone`, optionally call `/api/worknest/complete` only with a documented
  terminal `done` payload.
- On unrecoverable blocked state, optionally call `/api/worknest/complete` only
  with documented terminal `blocked` payload.
- Do not implement passive WorkNest queue dashboards through `next-task`,
  because that endpoint can claim work.

### P1: Documentation And Operator Clarity

- Update README with the chosen MVP default path and exact smoke commands.
- Add a short runbook section for:
  - config-service requirement;
  - UI startup;
  - plan preview;
  - approved run;
  - Live Runs inspection;
  - Human Review acceptance/rework;
  - WorkNest terminal completion.
- Mark old checklist items that are superseded by current implementation so a
  future agent does not chase stale unchecked sprint tasks.

### P2: Post-MVP Hardening

- Add latency/retry/failure metrics from the original plan's Day 3 checklist.
- Run 10-20 representative cases and record observed failure modes.
- Implement real Codex app-server daemon execution from compiled visual flow
  manifests, including isolated workspace creation.
- Add progress/workpad updates only after WorkNest exposes a documented
  external-agent capability for them.
- Decide whether mini-chat hidden warmup should be enabled; it is useful for
  latency but changes conversation state.
- Promote or remove legacy `launch-desk/` only after explicit product decision.

## Not MVP Blockers

- Image generation, web browsing, and arbitrary external tools are outside the
  current MVP tool contract.
- A separate registered daemon service is not required while the in-process
  runner and dispatcher replay satisfy the reviewable workflow.
- Full WorkNest queue browsing is not required until WorkNest exposes a safe
  read/list capability for external agents.
- Vector/semantic RAG is not required for this MVP; current project memory and
  tests are enough for the immediate product loop.

## Known Risk Areas

- Some sprint notes still contain unchecked items that are already implemented
  elsewhere; prefer current source, tests, README, and this consolidation note
  during the MVP pass.
- Real file-writing Codex workers can stop on approvals; the UI needs an
  explicit approval/blocker surface before this is a smooth happy path.
- WorkNest can be terminally updated through the bridge, but richer progress
  updates remain contract-blocked.
- Generated `.mini_orchestrator/` state is operational data, not durable product
  memory; keep only redacted summaries in project-memory.
