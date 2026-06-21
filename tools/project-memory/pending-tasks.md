# Pending Tasks

Use this file for active project-wide plans and multi-step work.

Keep entries concise and task-relevant. Do not store full diffs, large logs,
generated outputs, secrets, credentials, or private production data.

## Status Markers

- `[ ]` not started
- `[~]` in progress
- `[x]` done
- `[!]` blocked or needs attention

## Tasks

### Generated Project Artifact Isolation

Goal: make repeated orchestrator test runs create isolated, project-named
artifacts instead of modifying legacy or unrelated app folders.

- [x] Add dispatcher runtime prompt rules for generated app artifact folders.
- [x] Add regression tests that chain prompts mention artifact isolation.
- [x] Document the retry/debug workflow for real-token orchestrator runs.

### Dispatcher Chain Preset Execution Contract

Goal: make approved dashboard tasks execute through the selected agent chain
preset instead of the dispatcher hard-coded worker model list.

- [x] Preserve full chain preset agent settings from the dashboard payload.
- [x] Let dispatcher runs load worker profiles from the selected chain preset.
- [x] Record the selected chain execution contract in run logs and docs.
- [x] Verify focused dispatcher/UI tests.

### Live Runs Card Progress Indicator

Goal: show a compact, recorded-stage-based progress indicator on dashboard task
cards without inventing hidden runner progress.

- [x] Add a circular progress indicator to Kanban task cards.
- [x] Compute progress only from run status and visible stage statuses.
- [x] Add a focused dashboard UI regression assertion.
- [x] Verify the focused UI checks.

### Symphony-Governed Chain Dashboard Pass

Goal: make the dashboard show a Symphony-aware task workflow with selected
agent chain context, clickable agent details, and real Symphony daemon
observability.

Planned changes:

- [x] Confirm the current Symphony HTTP contract from `D:\AI\symphony\elixir`.
- [x] Add a mini-orchestrator Symphony run gateway record for approved requests
  while upstream Symphony exposes observability but not external intake.
- [x] Preserve the selected chain in the Symphony request/run payload.
- [x] Render Symphony-aware task cards and daemon summary cards in Live Runs.
- [x] Make current agent and stage chips open focused detail views.
- [x] Verify API, UI script parse, and a smoke workflow.

Risks or dependencies:

- Current Symphony exposes `GET /api/v1/state`, `POST /api/v1/refresh`, and
  `GET /api/v1/{issue_identifier}` only; actual task creation remains blocked
  until Symphony adds an agent-facing intake endpoint or tracker-backed task
  creation contract.

### Live Runs Task/Daemon Placement Fix

Goal: keep task cards in the upper Kanban and move Symphony daemon observability
cards into the lower daemon area.

Planned changes:

- [x] Filter `symphony-daemon` summary/snapshot records out of the Kanban task
  board.
- [x] Render Symphony daemon records in the lower dashboard area.
- [x] Keep gateway/dispatcher task cards in the Kanban columns.
- [x] Verify focused UI checks and script syntax.

Risks or dependencies:

- Symphony gateway task requests remain task cards; only daemon observability
  records move to the lower panel.

### Agent Builder Chain Preset Hygiene

Goal: keep chain preset management predictable in the browser-local Agent
Builder list.

- [x] Reject duplicate chain preset names when saving as a new preset.
- [x] Add a delete action for selected custom chain presets with confirmation.
- [x] Verify the focused Agent Builder UI checks.

### Agent Builder Card Layout Refresh

Goal: make visual agent cards compact, readable, and easier to connect.

- [x] Reduce card field overflow and remove horizontal scroll from cards.
- [x] Modernize connection ports and prevent port labels from overlapping form controls.
- [x] Verify the focused Agent Builder UI checks.

### Dashboard Chain Picker Placement

Goal: make the current execution chain visible and selectable from the dashboard
top bar.

- [x] Move plan mode and chain preset selection out of the task form.
- [x] Replace old plan/core-run buttons with one chain selection action.
- [x] Show the current selected chain next to the picker.
- [x] Verify the focused dashboard UI checks.

### Default Chain Preset Persistence Fix

Goal: keep edits to the built-in default chain preset when switching presets or
refreshing dashboard selectors.

- [x] Persist overwritten default chain presets in browser-local storage.
- [x] Load persisted default chain overrides in Agent Builder and Dashboard.
- [x] Verify the focused UI checks.

### Sprint7: Symphony Bridge Adapter Sprint

Goal: complete the WorkNest sprint
`2026-06-19_17-01-10_symphony-bridge-adapter-sprint` as one coherent MVP
runtime pass.

Planned changes:

- [x] Confirm task 001 source-mode work and preserve dispatcher visibility.
- [x] Define one normalized run-state shape across dispatcher, local daemon,
  and Symphony sources.
- [x] Mark stale dispatcher JSONL runs without hiding current active runs.
- [x] Add a Symphony bridge blocker endpoint for approved task-run intake.
- [x] Document the Symphony-side intake adapter responsibilities and limits.
- [x] Keep WorkNest as source and terminal completion sink after user review.
- [x] Verify the real Codex app-server chain remains visible in the dashboard.
- [x] Update README and project memory with source precedence, bridge limits,
  and smoke commands.

Risks or dependencies:

- WorkNest `sprint7` is a UI alias; manager API calls require the full sprint id.
- WorkNest terminal `done` should remain gated by user acceptance.

### MVP Consolidation And Remaining Work

Goal: consolidate the current mini-orchestrator implementation state and write
the remaining work needed for a reviewable MVP.

Planned changes:

- [x] Inventory current product surfaces, implementation modules, tests, and
  project-memory contracts.
- [x] Write a compact MVP status/roadmap document in project memory.
- [x] Verify the current test/syntax baseline where practical.
- [x] Update this checklist when the consolidation document is complete.

Risks or dependencies:

- Existing sprint notes may contain stale unchecked items; current source files,
  tests, and README are the authority for this pass.

### Backend Flow Storage Sprint Task

Goal: add backend persistence for visual agent flows so browser localStorage
remains draft/import state and executable workflow work can later use saved,
versioned server-side flows.

Planned changes:

- [x] Add flow storage/validation helpers for saved flow drafts.
- [x] Expose `/api/agent-flows` list/create/read/update endpoints.
- [x] Wire Agent Builder saves to backend persistence while preserving local
  editing.
- [x] Add focused tests for flow storage and HTTP API behavior.
- [x] Update durable workflow docs and complete the WorkNest sprint task.

Risks or dependencies:

- This task should not make browser-local flow state executable yet; daemon
  execution starts only after later validation/compile sprint tasks.

### Flow Validation Sprint Task

Goal: add server-side validation for saved executable flow drafts before later
compile and daemon execution steps consume them.

Planned changes:

- [x] Add precise validation errors/warnings with field paths.
- [x] Validate ids, required agent fields, supported runtime settings, graph
  references, one start node, and no cycles.
- [x] Expose `POST /api/agent-flows/{id}/validate`.
- [x] Add focused tests for valid default chain, broken links, and cycles.
- [x] Complete the WorkNest sprint task.

Risks or dependencies:

- Validation should not start workers or compile profiles; it is a gate for
  later sprint tasks.

### Compile Worker Profiles Sprint Task

Goal: compile a validated saved flow into an immutable run manifest and worker
profile snapshots without starting workers.

Planned changes:

- [x] Add compile helpers and immutable manifest storage.
- [x] Expose `POST /api/agent-flows/{id}/compile` with approval metadata.
- [x] Include manifest id, flow id/version, profile snapshots, graph, and
  runtime policy.
- [x] Add focused one-card and three-card compile tests.
- [x] Complete the WorkNest sprint task.

Risks or dependencies:

- Compile output is an approved artifact for later daemon tasks; it must not
  mutate the source flow or launch Codex workers.

### Approval And Run Manifest UI Sprint Task

Goal: add an explicit UI approval surface that shows what will run and creates
an immutable manifest without launching workers.

Planned changes:

- [x] Add Agent Builder approval controls and manifest preview.
- [x] Require explicit approval before compile.
- [x] Show selected task/context, flow, agent order, runtime settings, workspace
  policy, and first prompt summary.
- [x] Verify UI script parsing and focused tests.
- [x] Complete the WorkNest sprint task.

Risks or dependencies:

- Approval must create/select a manifest only; daemon execution starts in later
  sprint tasks.

### Single-Card Daemon MVP Sprint Task

Goal: add an in-process dry-run daemon runner for one compiled worker profile
without binding a new port or reading WorkNest files directly.

Planned changes:

- [x] Add local daemon run-state/event-log storage.
- [x] Add dry-run single-profile runner.
- [x] Expose run creation and local run-state through existing UI API surface.
- [x] Add focused tests for done run states and replayable events.
- [x] Complete the WorkNest sprint task.

Risks or dependencies:

- The MVP uses fake/dry-run transport only; real Codex app-server execution is a
  later integration step.

### Three-Agent Flow Runner Sprint Task

Goal: execute a compiled linear Planner -> Executor -> Reviewer manifest with
compact structured artifacts between nodes and a bounded reviewer verdict.

Planned changes:

- [x] Add dry-run manifest graph runner.
- [x] Persist per-node artifacts and reviewer verdict in run state/events.
- [x] Map verdicts to done, retrying, blocked, or failed.
- [x] Add simulated success and blocked runner tests.
- [x] Complete the WorkNest sprint task.

Risks or dependencies:

- This remains simulated transport; it must not launch real Codex or infer
  WorkNest state transitions beyond final task completion.

### Per-Node Live State Sprint Task

Goal: render daemon node state in Live Runs so users can inspect each card/node
instead of only the overall run.

Planned changes:

- [x] Normalize daemon `nodeStates` and `flowArtifacts` into UI stages.
- [x] Show per-node status, last event, output summary, artifact id, and verdict.
- [x] Mark blocked/failed/retrying node statuses from runner state.
- [x] Add focused runner/UI checks and JS parse.
- [x] Complete the WorkNest sprint task.

Risks or dependencies:

- UI must only render runner state; it must not infer hidden progress.

### WorkNest Lifecycle Bridge Sprint Task

Goal: connect the runner-facing lifecycle to WorkNest only through
config-service and the documented WorkNest external-agent contract.

Planned changes:

- [x] Add config-service-resolved WorkNest lifecycle bridge.
- [x] Read contract before `next-task` and `task-completed` calls.
- [x] Restrict completion to terminal `done` or `blocked`.
- [x] Expose explicit claim/complete UI API endpoints.
- [x] Add focused bridge tests.
- [x] Complete the WorkNest sprint task.

Risks or dependencies:

- No direct WorkNest storage reads, arbitrary task status transitions, or
  progress/workpad writes are supported without a future contract capability.

### Symphony-Style Kanban Live Run Cards

Goal: make the main dashboard show dispatcher live runs as task cards moving
through a compact Kanban board, so smoke tasks such as a dentistry CRM are
visible in the same mental model as Symphony/WorkNest cards.

Planned changes:

- [x] Render Live Runs as Backlog, Todo, In Progress, Human Review, and Done
  columns.
- [x] Place each dispatcher run card in the column implied by its current
  event/stage state.
- [x] Start a background dentistry CRM task and verify it moves through Todo,
  In Progress, Human Review, and Done.

Risks or dependencies:

- This remains dispatcher JSONL observability, not a real Symphony daemon or
  WorkNest task movement lifecycle.

### Live Runs Current Pipeline UX

Goal: make the dashboard emphasize the current task pipeline while keeping
completed runs available in a compact Done area.

Planned changes:

- [x] Add normalized run stage state for planner, executor, and reviewer.
- [x] Render active/current runs as a pipeline instead of debug cards.
- [x] Move completed runs into a compact Done folder/list.
- [x] Verify focused tests and UI smoke.

Risks or dependencies:

- Dispatcher logs are still the source of truth; the UI must not invent worker
  progress beyond recorded events.

### Visual Agent Access Mode

Goal: let each visual-agent card choose the Codex runtime access mode used by
its app-server thread/turn, with full access as the temporary default.

Planned changes:

- [x] Add an access selector to agent cards and settings.
- [x] Persist access mode in agent card snapshots and mini-chat payloads.
- [x] Map access mode to Codex app-server `approvalPolicy`, thread `sandbox`,
  and turn `sandboxPolicy`.
- [x] Verify focused UI/API tests and syntax checks.

Risks or dependencies:

- Full access intentionally removes Codex sandbox boundaries. This is a
  temporary local default for workflow testing and should stay visible in the
  card UI.

### Live Runs Dashboard MVP

Goal: make the current mini-orchestrator UI show Symphony-style daemon run
state before a real daemon loop exists.

Planned changes:

- [x] Add a small API surface for daemon run-state records.
- [x] Render active run cards on the main dashboard.
- [x] Keep the MVP read-only and backed by demo/schema-shaped run states.
- [x] Verify Python syntax, focused tests, and HTTP smoke.

Risks or dependencies:

- This is an observability surface only. It must not claim WorkNest tasks, bind
  new ports, or launch real Codex workers until the daemon lifecycle is added.

### Live Workflow Progress Gap

Goal: make an approved dispatcher workflow visible end-to-end in the UI, not
only as a synchronous final JSON response.

Observed during calculator smoke on 2026-06-18:

- [x] Real plan preview reached a planner worker and returned an approval plan.
- [x] Route UI dispatcher requests through UTF-8 task files so Russian task
  text reaches worker prompts without question marks.
- [!] Full real chain reached the executor but stopped on Codex file-change
  approval; the parent API timed out while waiting for the turn.
- [x] The open UI tab polls dispatcher JSONL live-run state instead of relying
  only on the synchronous response from the initiating request.
- [x] Add a live run-state model for dispatcher events, approvals, worker
  status, and final artifacts.
- [x] Use the calculator task as the recurring smoke test for plan, run-state,
  approval visibility, and reviewer verification.
- [x] Verify a background dry-run calculator chain reaches `done` in Live Runs.
- [x] Verify a real read-only calculator inspection chain shows planner ->
  executor -> reviewer progress and reaches `done` in Live Runs.

Risks or dependencies:

- Real file-writing workers need an explicit approval strategy. The UI should
  either surface the approval gate or run only approved/safe dry-run demos.

### Codex Worker Chat Project Routing

Goal: route Codex worker chats spawned by the mini-orchestrator UI into a
separate technical project folder while preserving the real project as the
execution target.

Planned changes:

- [x] Configure `D:\AI\orchestrator-worker-chats` as the worker chat root.
- [x] Start Codex app-server from the worker chat root when configured.
- [x] Keep dispatcher turns pointed at the mini-orchestrator target workspace.
- [x] Show worker chat root and target workspace in logs/Tech output.
- [x] Verify focused tests and restart the UI.

Risks or dependencies:

- Codex sidebar grouping depends on app-server workspace behavior. The first
  live real-planner smoke confirmed the transport starts from the technical
  project and keeps `mini-orchestrator` as the target workspace.

### Dispatcher Worker Debug Section

Goal: keep the fast Codex app-server worker path visible and debuggable from
the mini-orchestrator UI without hiding or slowing worker sessions.

Planned changes:

- [x] Add a technical/debug summary for dispatcher worker runs.
- [x] Show worker runtime, log, timing, thread, and event metadata in a separate
  UI tab.
- [x] Verify focused syntax and UI/API checks.

Risks or dependencies:

- This does not hide worker chats from the Codex sidebar; it adds a dedicated
  mini-orchestrator debug surface for the same fast execution path.

### Codex Worker Primary LLM Path

Goal: make the Codex app-server dispatcher the primary LLM channel for visual
agent UI helpers while OpenAI API keys/direct Responses calls remain deferred.

Planned changes:

- [x] Record that work-package translation uses dispatcher/Codex worker first.
- [x] Remove direct OpenAI translation from the active UI translation path.
- [x] Research dispatcher/Codex worker latency and optimization options.
- [x] Verify focused tests for the agent API and dispatcher-facing UI path.

Verification:

- [x] Run focused agent API tests.
- [x] Run Python syntax checks for changed modules.

### Persistent Codex App-Server Experiment

Goal: reduce visual-agent helper latency by reusing one Codex app-server process
inside the UI runtime.

Planned changes:

- [x] Skip transient translation cache; future successful translations belong
  in durable DB storage.
- [x] Add a persistent Codex dispatcher manager for single-worker UI helper
  requests.
- [x] Keep plan-only, dry-run, and full-chain workflows on the isolated
  subprocess dispatcher path.
- [x] Add timing events around persistent app-server readiness, thread start,
  and turn completion.
- [x] Add compact prompt and helper-thread reuse only for translation helper
  requests.
- [x] Verify persistent translation behavior against a running Codex app-server.

Verification:

- [x] Run focused agent API tests.
- [x] Run Python syntax checks for changed modules.
- [x] Run a live two-translation smoke through `PersistentCodexDispatcher`:
  first request 12.87s, second request 1.37s with helper-thread reuse.

### Bootstrap Instruction Kit

Goal: initialize local agent instructions from `D:\AI\general-instructions`.

Planned changes:

- [x] Copy root `AGENTS.md`, working agreements, runbook, startup script, and
  project-memory templates.
- [x] Record instruction-kit provenance and local GI source path.
- [x] Add ignore rules for local/generated agent memory and runtime noise.

Execution order:

- [x] Inspect source instruction library and target project state.
- [x] Apply project-local bootstrap files.
- [x] Run startup restore as a smoke check.

Risks or dependencies:

- [!] Runtime stack and package layout are still undecided.

Verification:

- [x] `.\tools\agent-start.ps1` completed successfully.

### MVP Mini-Orchestrator

Goal: implement a working plan -> execute -> validate MVP in this repository.

Planned changes:

- [x] Create runtime scaffold for Python CLI (`mini_orchestrator/` package and entrypoint).
- [x] Add core data model (`TaskState`), router, planner, executor, validator, and logs.
- [x] Restrict execution to allowlisted tools: `read_file`, `search`, `apply_patch`, `run_command`.
- [x] Add a minimal runner command (`python -m mini_orchestrator`) with sane defaults and limits.
- [x] Add README and project startup docs (install/run) so the stack is defined.

Execution order:

- [x] Parse plan intent and translate to MVP route (координатор + исполнение + валидация).
- [x] Implement bounded execution loop with `max_iterations` and `max_retries`.
- [x] Add JSON event logging and summary output.
- [x] Update pending task checklist to Done after implementation.

Risks or dependencies:

- External LLM calls are not yet integrated; planner/executor behavior is rule-based for MVP.
- Safety policy currently relies on repository-root path allowlist and command timeout/output limits.

Verification:

- [ ] Run a smoke command for a simple read/search/apply workflow.

### LLM Coordinator Layer

Goal: add the first LLM-backed coordinator/planner layer while preserving the
safe rule-based fallback.

Planned changes:

- [x] Add provider/model configuration for an OpenAI-compatible LLM client.
- [x] Add an LLM planner that returns only allowlisted tool actions.
- [x] Add a safe direct-response action for natural-language requests.
- [x] Document required environment variables and fallback behavior.

Verification:

- [x] Run rule-based fallback smoke checks without an API key.
- [x] Verify LLM mode reports a clear missing-key error when configured.

### Codex-Native Orchestrator Sprint

Goal: build the Codex-native orchestrator MVP using project custom agents,
Codex SDK/app-server dispatcher flow, event replay records, and WorkNest as the
task lifecycle manager.

Planned changes:

- [x] Define Codex custom agents for planner, executor, and reviewer roles.
- [x] Add a dispatcher prototype under `tools/codex-dispatcher/`.
- [x] Document and implement the orchestrator event protocol.
- [x] Integrate WorkNest as queue/lifecycle API, not as an executor.

Verification:

- [x] Ask WorkNest for each next task and complete tasks through
  `/agent-intake/task-completed`.
- [x] Run lightweight local checks for added scripts where possible.

### Dispatcher Decision Layer

Goal: add the smallest explicit dispatcher decision object that selects exactly
one worker role for an incoming task.

Planned changes:

- [x] Add an inspectable dispatch decision with role, reason, confidence, and
  next input.
- [x] Route planner-directed and ambiguous tasks to `planner`.
- [x] Add a smoke test for planner routing and ambiguous fallback.

Verification:

- [x] Run focused dispatcher smoke tests.

### Dispatcher Role Routing Increment

Goal: add the next narrow dispatcher routing increment for explicit executor
and reviewer requests while preserving planner fallback for ambiguous work.

Planned changes:

- [x] Define minimal executor and reviewer routing markers.
- [x] Keep ambiguous tasks routed to `planner`.
- [x] Add focused tests for executor and reviewer selection.
- [x] Update dispatcher docs to describe the explicit routing rules.

Verification:

- [x] Run focused dispatcher tests.

### GI Config-Service UI Startup

Goal: make the web UI obey GI config-service rules for runtime ports and
service discovery.

Planned changes:

- [x] Add project-local runtime config with `service_id` and config-service
  bootstrap behavior.
- [x] Resolve UI host/port from live config-service before binding.
- [x] Fail with a clear blocker when the service record is missing or
  incomplete instead of guessing a fallback port.
- [x] Document the startup contract and verification commands.

Verification:

- [x] Run compile checks.
- [x] Verify missing `mini-orchestrator` service record blocks UI startup.
- [x] Run syntax checks for dispatcher modules.

### Orchestrator Chat Command Contract

Goal: allow early project testing by sending chat commands such as
`оркестратор план Сделай калькулятор`, while the dispatcher still selects only
one worker per run.

Planned changes:

- [x] Record the chat command contract in project memory.
- [x] Add parser support for `оркестратор` / `orchestrator` command prefixes.
- [x] Add explicit role aliases for planner, executor, and reviewer commands.
- [x] Add focused tests and documentation.

Verification:

- [x] Run focused dispatcher tests.
- [x] Run dry-run smoke commands for planner-forced and default task routing.

### Agent Settings Builder MVP

Goal: add a visual agent-flow constructor to the Web UI.

Planned changes:

- [x] Add a main UI button that opens the agent settings builder.
- [x] Add a dedicated builder page with a left control panel and central flow workspace.
- [x] Add configurable agent cards with LLM, speed, and reasoning settings.
- [x] Add draggable cards, connection ports, flexible arrows, and local JSON state.
- [x] Document the next backend integration contract for saving, validating, and running flows.

Verification:

- [x] Run Python syntax checks.
- [x] Smoke-check `/`, `/agents-builder`, and `/health`.
- [x] Browser-check card creation, dragging, connecting, and local JSON state.

### Dispatcher Full Chain Increment

Goal: add an explicit planner -> executor -> reviewer -> final dispatcher mode
while preserving the current one-worker routing mode for narrow tests.

Planned changes:

- [x] Add a chain execution mode to the dispatcher CLI.
- [x] Pass planner output into executor and executor output into reviewer.
- [x] Keep dry-run chain output inspectable without launching Codex.
- [x] Update event protocol, README, and tests.

Verification:

- [x] Run focused dispatcher tests.
- [x] Run dry-run smoke for `оркестратор план Сделай калькулятор --chain`.
- [x] Run syntax checks for dispatcher modules.

### Dispatcher Local Test Project Mode

Goal: allow an explicitly requested real demo execution path that creates a
bounded project under `test-projects/`, writes code, and verifies it without
launching a broad Codex worker.

Planned changes:

- [x] Add a constrained local test project mode to the dispatcher CLI.
- [x] Support a first `calculator` demo project with generated code and tests.
- [x] Keep generated projects inside the repository-local `test-projects/`
  boundary.
- [x] Update docs and command contract.

Verification:

- [x] Run focused dispatcher tests.
- [x] Run a real local calculator project smoke command.

### Dispatcher Chat Approval Workflow

Goal: make `orchestrator plan <task>` a chat-gated workflow: first return a
plan for user approval, then after explicit confirmation run implementation,
test review, fix loops, final review, and application launch.

Planned changes:

- [x] Add dispatcher plan-only output for chat approval.
- [x] Update local test project execution to run executor -> test/review loops.
- [x] Add tests for plan-only and bounded review loop behavior.
- [x] Update AGENTS, docs, and project-memory contract.

Verification:

- [x] Remove the generated calculator test project.
- [x] Run focused dispatcher tests.
- [x] Run plan-only calculator command.
- [x] Run approved local calculator workflow from a clean test project folder in
  a temporary test directory.

### Dispatcher Plan-only Generalization Fix

Goal: prevent `--plan-only` from reusing the calculator-only local demo plan for
unrelated tasks or crashing before approval.

Planned changes:

- [x] Keep calculator-only behavior scoped to `--local-test-project`.
- [x] Return a generic chat approval plan for unsupported local demo tasks.
- [x] Route UI-described plan requests away from the CLI calculator template.
- [x] Return structured JSON errors for expected dispatcher mode failures.

Verification:

- [x] Run focused dispatcher tests.
- [x] Run plan-only calculator, calculator-with-UI, and marketplace-agent smoke
  commands.
- [x] Run unsupported `--local-test-project` smoke and confirm JSON error output
  instead of traceback.

### Dispatcher Plan-only Planner Worker Fix

Goal: make real `--plan-only` use the planner worker instead of returning a
local generic template.

Planned changes:

- [x] Build a plan-only prompt from planner instructions and the user task.
- [x] Run Codex app-server planner turn for `--plan-only` unless `--dry-run` is
  set.
- [x] Keep local fallback approval plans only for `--plan-only --dry-run`.
- [x] Make JSON CLI output robust when planner responses contain Unicode that
  the Windows console encoding cannot print.

Verification:

- [x] Run focused dispatcher tests.
- [x] Run real plan-only marketplace-agent command and confirm task-specific
  planner output.
- [x] Run real plan-only Word Office MVP command and confirm a different
  task-specific planner output.

### Dispatcher Construction CRM Local Demo

Goal: allow an approved `orchestrator plan` task for a construction-store CRM to
run through the bounded local test project workflow instead of failing with the
calculator-only guard.

Planned changes:

- [x] Add construction-store CRM task detection for local demo project mode.
- [x] Add generated project files with CRM domain logic, seed data, tests, and a
  launch/smoke command.
- [x] Update dispatcher docs and chat-command contract.
- [x] Add focused dispatcher test coverage.

Verification:

- [x] Run focused dispatcher tests.
- [x] Run the approved construction CRM local workflow and confirm final smoke.

### Dispatcher UI Smoke Review Gate

Goal: make local test project review catch inert browser UIs, especially CRM
buttons that render but do not do anything.

Planned changes:

- [x] Add a UI smoke check step to local test project review output.
- [x] Make construction CRM generation include a UI smoke contract and working
  button/view behavior.
- [x] Update dispatcher tests and docs so review pass requires UI smoke when a
  demo project declares it.

Verification:

- [x] Run focused dispatcher tests.
- [x] Run approved construction CRM workflow and confirm `UI smoke` is reported.

### Mini-Orchestrator Web UI Replacement

Goal: replace the stale Campaign Concept Studio page with an actual
mini-orchestrator UI for the current chat-gated dispatcher workflow.

Planned changes:

- [x] Add narrow UI API endpoints for plan preview and approved local demo run.
- [x] Replace `mini_orchestrator/web/index.html` with an orchestrator dashboard.
- [x] Document the new UI/API behavior.
- [x] Run server/API smoke checks and focused dispatcher tests.

Verification:

- [x] Health endpoint responds.
- [x] Plan endpoint returns a dry-run approval plan without creating files.
- [x] Approved local demo endpoint returns dispatcher outputs.
- [x] Frontend page no longer contains Campaign Concept Studio content.

### Agent Flow Builder Editing Sprint

Goal: turn the browser-local agent flow builder into a clearer graph editor
where users add agents, edit connections, understand multiple incoming arrows,
and save a regenerated flow model from the visible cards and arrows.

Planned changes:

- [x] Collapse the sidebar creation controls to a single `Добавить агента`
  action.
- [x] Replace raw JSON textarea with a readable flow summary and compact JSON
  preview.
- [x] Add connection selection, reattach controls, and delete action.
- [x] Visually separate multiple incoming arrows to the same agent.
- [x] Rebuild and persist the JSON model only from the visible flow when
  `Сохранить` is clicked.

Verification:

- [x] Run syntax/static checks for the updated builder page.
- [x] Smoke the builder with HTTP and DOM-invariant checks.

### Agent Flow Builder Branch Outputs

Goal: make every agent card work like a flowchart block with two separate
outcomes: `успех` and `не успех`.

Planned changes:

- [x] Add two output ports to each card.
- [x] Store selected outgoing branch in `connection.fromPort`.
- [x] Allow editing the selected connection's outgoing branch.
- [x] Show branch labels in the readable flow summary and JSON preview.
- [x] Update project-memory flow contract.

Verification:

- [x] Run builder JavaScript syntax and DOM-invariant checks.
- [x] Run Python compile check for the package.

### Agent Card Mini Chat

Goal: let the user test how each visual agent card talks through its selected
LLM from the application UI.

Planned changes:

- [x] Add a backend chat endpoint for one agent card.
- [x] Send selected `llm`, `role`, `speed`, and `reasoning` from the builder UI.
- [x] Render a compact mini chat inside each agent card.
- [x] Keep `rules` agents clearly non-LLM instead of pretending to call a model.

Verification:

- [x] Run focused syntax/compile checks.

### Agent API Module And Work Package Translation Timing

Goal: split visual-agent chat backend behavior out of the web UI handler and
make work-package helper translation update after the user leaves a prompt
field, not on every keystroke.

Planned changes:

- [x] Add a focused backend module for the visual agent chat API.
- [x] Keep `/api/agents/chat` behavior compatible through the existing UI
  route.
- [x] Update work-package textareas so draft text is stored during editing and
  translation refresh waits for field blur.
- [x] Run focused syntax and unit checks.

Follow-up changes:

- [x] Store edited work-package text together with its generated translation.
- [x] Prefer saved field translations, then built-in dictionary translations,
  then remote agent translation for unknown text.
- [x] Persist generated translations when agent or preset settings are saved.

### Dispatcher Worker Model Defaults

Goal: make real Codex dispatcher runs pass the selected worker model to Codex
app-server by default.

Planned changes:

- [x] Make `--use-worker-models` the CLI default.
- [x] Add `--use-codex-default-models` as the explicit opt-out.
- [x] Update dispatcher documentation.

Verification:

- [x] Run focused dispatcher tests.

### Agent Card Runtime Identity Debugging

Goal: make each visual agent card show and return the selected model/runtime
identity clearly enough to debug which LLM answered.

Planned changes:

- [x] Add a compact Codex-like model/reasoning badge to agent cards.
- [x] Return speed/reasoning metadata from the agent mini-chat endpoint.
- [x] Show model/speed/reasoning metadata beside mini-chat answers.

Verification:

- [x] Run focused syntax/compile checks.

### Translation Helper Runtime Boundary

Goal: keep work-package translation as application UI helper behavior instead
of inheriting the model selected for workflow agent cards.

Planned changes:

- [x] Make the backend choose a dedicated translation helper model.
- [x] Stop sending the selected card LLM as the translation model from the UI.
- [x] Update focused tests and project-memory behavior notes.

Verification:

- [x] Run focused agent API tests.
- [x] Run compile checks for touched Python modules.

### Persistent Visual Agent Mini-Chat

Goal: make mini-chat exercise the actual selected visual agent without routing
each message through a cold dispatcher/planner wrapper.

Planned changes:

- [x] Add a persistent per-card Codex thread path for mini-chat.
- [x] Put card/work-package instructions into thread developer instructions.
- [x] Send ordinary user messages to the existing thread instead of wrapping
      every turn in a full dispatcher worker prompt.
- [x] Keep dispatcher fallback for tests and non-UI callers.

Verification:

- [x] Run focused agent API tests.
- [x] Run compile checks for touched Python modules and dispatcher transport.

Follow-up decision:

- [ ] Decide whether mini-chat warmup should run a hidden priming turn. This
      makes the next real user message fast, but it adds hidden conversation
      state and can make immediate sends wait longer.

### GI Refactor Sprint

Goal: execute the scoped refactor plan in
`tools/project-memory/refactor-battle-plan-2026-06-17.md`.

Planned changes:

- [x] Harden package-native tool guardrails and search exclusions.
- [x] Introduce a safe command execution adapter.
- [x] Move stale Campaign Concept Studio API/code out of the active product
  surface.
- [x] Make the UI planner preview use a real planner worker, with explicit
  demo/dry-run mode.
- [x] Split `tools/codex-dispatcher/dispatcher.py` into focused modules with
  dependency injection and signal/event boundaries.
- [x] Move `launch-desk` into a legacy/experimental boundary and make any
  retained runnable service obey GI config-service startup rules.

Verification:

- [x] `python -m compileall mini_orchestrator tools\codex-dispatcher`
- [x] `python tools\codex-dispatcher\test_dispatcher.py`
- [x] `python -m mini_orchestrator "search AGENTS" --no-log`
- [x] UI handler smoke for real/demo plan preview contract and removed
  `/api/campaign`; live `/health` responded on the configured UI port.
- [x] Launch Desk precise blocker recorded: backend/frontend `tsc.cmd` and
  `vitest.cmd` shims are missing until dependencies are restored.

### Dispatcher Release Architecture Refactor

Goal: finish the dispatcher split into release-oriented modules and remove local
demo project generation from the active dispatcher/UI surface.

Planned changes:

- [x] Move Codex app-server transport out of `dispatcher.py`.
- [x] Move dispatcher pipeline orchestration out of `dispatcher.py`.
- [x] Move CLI parsing/output out of `dispatcher.py`.
- [x] Remove `--local-test-project`, `test-projects/` generator code, and
  calculator/construction CRM demo templates from active release code.
- [x] Update UI approved workflow to run the real dispatcher chain instead of
  local demo mode.
- [x] Update README, dispatcher docs, event protocol, and chat command contract.
- [x] Update tests to cover release dispatcher behavior without demo generation.

Verification:

- [x] `python -m compileall mini_orchestrator tools\codex-dispatcher`
- [x] `python tools\codex-dispatcher\test_dispatcher.py`
- [x] `python -m pytest tests`
- [x] `python -m mini_orchestrator "search AGENTS" --no-log`
- [x] Dispatcher CLI smoke: `--plan-only --dry-run`.
- [x] Dispatcher CLI smoke: `--chain --dry-run`.
- [x] Removed CLI flag check: `--local-test-project` is rejected by argparse.
- [x] Live UI restart not run: config-service was unavailable and
  `service-runtime.json` has `self_registration=off`, so binding a fallback port
  would violate the project startup contract.

### Agent Presets And Work Packages

Goal: make visual agent roles behave as editable orchestration presets instead
of only card labels.

Planned changes:

- [x] Replace role-only agent creation with preset-based creation/selection for
  planner, executor, reviewer, generic agent, and custom agents.
- [x] Add an agent settings window that exposes runtime settings and the work
  package prompt fields: role/instructions, current objective, inputs/artifacts,
  constraints, previous agent outputs, allowed tools/actions, and expected
  output format.
- [x] Persist work-package fields with each visual agent card.
- [x] Keep the mini-chat focused on testing an agent's selected settings, not
  executing the visual workflow.

Verification:

- [x] Run focused syntax/compile checks.

### Runnable Dental CRM Demo

Goal: create a standalone dental CRM demo that shows the product surface agents
should eventually generate and modify.

Planned changes:

- [x] Add `.mini_orchestrator/test-runs/dental-crm-demo/index.html`.
- [x] Include seed patients, appointments, treatment statuses, and admin-task
  Kanban.
- [x] Keep it runnable by opening `index.html` directly in a browser.
- [x] Document demo usage next to the HTML file.
- [x] Verify the HTML and inline JavaScript parse cleanly.

Definition of done:

- [x] A user can open the demo and see patient cards, schedule, treatment
  progress, and admin tasks without starting a server.
- [x] The demo is suitable as the visible product target for the next
  visual-agent-card execution layer.

Verification:

- [x] `node -e "<inline script parse check>"`
- [x] `python -m pytest tests`

### Default Visual Agent Card Execution

Goal: choose one default visual agent card and run the dental CRM task through
that card as a compiled worker profile.

Planned changes:

- [x] Define a default `Dental CRM Builder` visual agent card.
- [x] Persist the selected card on the backend.
- [x] Validate and compile the card into an immutable worker-profile snapshot.
- [x] Add a run path that executes the dental CRM task through the compiled
  visual agent profile.
- [x] Make the resulting JSONL run visible in Live Runs as the selected card.

Definition of done:

- [x] The default card can be retrieved, persisted, compiled, and run from the
  backend.
- [x] A dental CRM task run produces a dispatcher JSONL event log with the
  selected card name as the worker stage.
- [x] Focused tests and syntax checks pass.

Verification:

- [x] `python -m pytest tests`
- [x] `python -m compileall mini_orchestrator`
- [x] Dental CRM run through `Dental CRM Builder` completed with
  `mode=visual-agent-task` and profile snapshot
  `worker-profile-dental-crm-builder-5301d5ba3d6ea2b0`.

### Superseded: Agent Builder Selected Card Run

Goal: let the Agent Builder UI start execution through the currently selected
visual card instead of relying on an implicit backend default card.

Decision update, 2026-06-18:

- [x] Removed this as a user-facing Agent Builder workflow. The builder is now
  only a constructor for saving agent-chain presets; execution belongs in the
  main Kanban/Live Runs workflow where the user selects which chain preset runs
  the task in `In Progress`.

### Symphony Service Discovery Bridge

Goal: connect Mini Orchestrator to the configured Symphony service through
GI config-service instead of only a hard-coded local state URL.

Planned changes:

- [x] Resolve the Symphony service record through config-service when
  `MINI_ORCHESTRATOR_DAEMON_STATE_URL` is not explicitly set.
- [x] Keep the existing environment override for local/manual daemon URLs.
- [x] Add local API helpers for Symphony refresh and issue detail endpoints
  exposed by the current Symphony implementation.
- [x] Keep task intake blocked until Symphony exposes a documented task-intake
  contract.
- [x] Update docs and tests for the connected-service behavior.

Verification:

- [x] Focused Symphony daemon tests.
- [x] `python -m pytest tests/test_symphony_daemon.py`
- [x] `python -m compileall mini_orchestrator`
- [x] `python -m pytest tests`
- [x] Live check: `/api/daemon/runs?source=symphony` resolved
  `http://127.0.0.1:4000/api/v1/state` through config-service and returned an
  empty current Symphony run summary.
- [x] Live check: `/api/symphony/refresh` returned a queued Symphony refresh
  response with `operations=["poll","reconcile"]`.

Historical implementation:

- [x] Previously added a visible selected-card run action to the builder UI.
- [x] Send the selected card's runtime settings and work package to
  `/api/agents/run` with explicit approval.
- [x] Keep the current default dental CRM card as the temporary runnable target
  when the user has not built another card yet.
- [x] Surface the returned visual-agent run id/profile in the builder status so
  the dashboard daemon/live-runs view can observe it.

Definition of done:

- [x] Running from Agent Builder uses a selected visual card payload, producing
  `mode=visual-agent-task` instead of the generic `/api/run` backend default
  path.

Verification:

- [x] `node -e "<inline script parse check>"`
- [x] `python -m pytest tests`
- [x] `python -m compileall mini_orchestrator`

### Live Runs Rework Action

Goal: make the Human Review `Доработки` action start a new visible background
run instead of only storing a local review label.

Planned changes:

- [x] Build a rework task from the selected completed run.
- [x] Post the rework task to `/api/dispatcher/run` with `approved=true` and
  `background=true`.
- [x] Keep the original reviewed card marked as `Доработки` while the new run
  appears in `In Progress`.
- [x] Add a focused dashboard UI regression assertion.

Verification:

- [x] Static dashboard test for the rework runner.
- [x] `python -m pytest tests/test_agent_builder_ui.py`
- [x] `node -e "<inline script compile check>"`

### Approved Workflow Turn Timeout

Goal: prevent full UI-approved dispatcher chains from failing at the CLI
default 90-second agent-turn timeout during real executor file work.

Completed changes:

- [x] Set approved dashboard workflow turns to 300 seconds.
- [x] Pass `--turn-timeout-seconds` for background `/api/dispatcher/run`.
- [x] Pass the same turn timeout for foreground approved dispatcher runs.
- [x] Restarted local UI so the updated backend code is active.
- [x] Verified a new CRM run moved past executor and completed all stages.

Verification:

- [x] `python -m pytest tests/test_agent_builder_ui.py`
- [x] `python -m compileall mini_orchestrator/ui.py`
- [x] Run `ui-0e5817571207` completed planner -> executor -> reviewer.

Follow-up implementation:

- [x] Add the same chain preset dropdown to the executable dashboard task form.
- [x] Send the selected chain preset with approved workflow runs.
- [x] Record selected chain metadata in dispatcher JSONL logs.
- [x] Render selected chain stages inside the single Live Runs task card.
- [x] Fix Builder load-chain feedback so the load message is not immediately
  overwritten by the generic ready status.

Follow-up verification:

- [x] `node -e "<inline script parse check for index and agents-builder>"`
- [x] `python -m pytest tests`
- [x] `python -m compileall mini_orchestrator`

### Agent Chain Presets

Goal: make the configured agent chain a selectable preset, with a default chain
and user-named saved chains from Agent Builder.

Planned changes:

- [x] Add a chain preset dropdown to Agent Builder.
- [x] Provide a default planner -> executor -> reviewer chain.
- [x] Save the current visible cards/connections as a named chain preset.
- [x] Reload saved chain presets from browser storage.

Definition of done:

- [x] A user can choose the default chain or a saved named chain from the
  dropdown, and saving the current chain adds or updates a named preset.

Verification:

- [x] `node -e "<inline script parse check>"`
- [x] `python -m pytest tests`
- [x] `python -m compileall mini_orchestrator`

### Compiled Flow Human Review Gate

Goal: make approved compiled-flow daemon runs land in Human Review first, then
record the user's `ToDone` or `Доработки` decision durably in local run state.

Planned changes:

- [x] Map successful compiled-flow dry-run completion to `review` instead of
  terminal `done`.
- [x] Add a local run review-decision API for daemon run state files.
- [x] Wire dashboard `ToDone` / `Доработки` actions to the backend decision API
  for local daemon runs.
- [x] Keep WorkNest terminal completion separate and gated by explicit
  acceptance.

Verification:

- [x] Focused daemon run tests for `review`, `done`, and `rework`.
- [x] Dashboard static/API tests for durable review actions.
- [x] `python -m compileall mini_orchestrator`

### Runtime SQLite Store

Goal: move `.mini_orchestrator/` runtime state into SQLite, keeping
`.mini_orchestrator/test-runs/` as the only file artifact tree.

Planned changes:

- [x] Inventory runtime folders and assign each to a storage theme.
- [x] Add a project-local SQLite schema for agent profiles, flow drafts,
  manifests, daemon/symphony run state, dispatcher tasks/process output, and
  generic runtime blobs/logs.
- [x] Add an idempotent migration command that imports all non-`test-runs`
  files into SQLite with source path, theme, content type, and timestamps.
- [x] Update code paths that create new flow/manifest/task/process/profile
  state to prefer SQLite where the current runtime contract is clear.
- [x] Verify migration counts and focused tests.

Definition of done:

- [x] Existing non-`test-runs` runtime files are represented in SQLite.
- [x] New writes for supported runtime themes go through SQLite instead of
  creating more ad hoc files.
- [x] File-based `test-runs/` behavior is unchanged.

Verification:

- [x] `python tools\migrate_runtime_to_sqlite.py`
- [x] `python tools\migrate_runtime_to_sqlite.py --prune-files`
- [x] `.mini_orchestrator/` now contains only `runtime.sqlite3` and
  `test-runs/`.
- [x] `python -m pytest tests tools\codex-dispatcher\test_dispatcher.py`
- [x] `python -m compileall mini_orchestrator tools\codex-dispatcher tools\migrate_runtime_to_sqlite.py`
