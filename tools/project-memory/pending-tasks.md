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
- [x] Run syntax checks for dispatcher modules.
