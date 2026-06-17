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
