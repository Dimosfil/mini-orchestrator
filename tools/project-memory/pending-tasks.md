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
