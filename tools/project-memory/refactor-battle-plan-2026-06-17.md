# Refactor Battle Plan: GI Compliance And Runtime Split

Date: 2026-06-17

WorkNest intake:

- Initial incorrect payload used `type= sprint` and was only stored:
  `2026-06-17T11-33-45-684Z_codex_8eb11fc4-faa8-433e-93f8-6b7c21d52f8c`.
- Corrected payload used `type= plan` and created an active sprint:
  `2026-06-17T11-35-58-013Z_codex_ceddd5f1-1dbf-408d-aac5-20d0e4f1c126`.
- WorkNest sprint id:
  `2026-06-17_14-35-58_gi-refactor-sprint-спринт-gi-рефакторинга`.
- Status returned by `/agent-intake/raw`: `ready`, `sprintStatus=active`.

## Goal

Bring the mini-orchestrator runtime closer to GI rules without changing the
user-visible workflow in one risky rewrite.

The sprint should preserve the current Python UI, dispatcher contract, local
demo workflow, and agent builder behavior while reducing hidden coupling and
making runtime boundaries explicit.

## Work Order

### 1. Core Tool Guardrails

Objective: make package-native tools safer and less noisy.

- Add generated/noise exclusions to `ToolRuntime._search`, including `.git`,
  `.venv`, `__pycache__`, `node_modules`, lockfiles, generated logs, RAG indexes,
  and local demo outputs.
- Keep search bounded by allowed workspace roots and output limits.
- Add focused tests for search exclusions and path boundaries.
- Review `read_file` behavior so large/generated files are not read in full by
  default when a safer bounded read is enough.

Definition of done:

- `python -m mini_orchestrator "search AGENTS" --no-log` no longer reports
  `.git`, `__pycache__`, or lockfile hits.
- Focused Python tests cover search exclusions and root boundaries.

### 2. Safe Command Adapter

Objective: move command execution policy out of ad hoc `shell=True` execution.

- Introduce a small command execution adapter for package-native tools.
- Prefer explicit argv commands when possible.
- Preserve current `run_command` user-facing behavior for simple smoke commands.
- Add Windows policy checks and clear blockers for destructive or ambiguous
  commands.
- Keep timeout and output limits centralized.

Definition of done:

- Existing CLI smoke still works.
- Tests cover empty command, timeout/error handling, and blocked destructive
  examples.

### 3. Product Surface Cleanup

Objective: remove stale product surfaces from the active UI/API.

- Move the old Campaign Concept Studio API path and campaign/image helper code
  into a clearly marked legacy module or remove it from active routing.
- Keep README and `/agent/contract` aligned with active endpoints only.
- Preserve the current orchestrator dashboard, agent builder, core run,
  dispatcher plan/run, and mini-chat endpoints.

Definition of done:

- `/api/campaign` is no longer part of the active service contract.
- Any retained campaign code is isolated under a legacy boundary and not loaded
  by the default UI route.

### 4. Real Planner Worker For UI Plan

Objective: make the dashboard plan preview capable of using the real planner
worker instead of always using `--dry-run`.

- Add an explicit UI/API mode for real planner preview.
- Keep a demo/dry-run path available only when clearly labelled as demo.
- Call dispatcher `--plan-only` without `--dry-run` for real planner previews.
- Return planner errors as structured UI errors.

Definition of done:

- `/api/dispatcher/plan` can run a real planner worker when requested or by
  configured default.
- Dry-run behavior remains available and explicit.

### 5. Dispatcher Module Split

Objective: split the 2000+ line dispatcher by meaning with minimal coupling.

Target module boundaries:

- `models`: worker, decision, command result, chat command data structures.
- `routing`: chat command parsing and dispatch decision rules.
- `events`: event types, JSONL writer, protocol validation.
- `codex_app`: Codex app-server transport and turn collection.
- `prompts`: worker prompt and plan-only prompt builders.
- `local_demo`: local demo selection, generated project writers, smoke/review
  loop.
- `worknest_client`: task-manager discovery and WorkNest intake/completion.
- `pipeline`: orchestration modes that compose routing, events, codex transport,
  local demo, and WorkNest.
- `cli`: argument parsing and final JSON output.

Communication rule:

- Prefer dependency injection for filesystem roots, runs dir, workers, command
  runner, and Codex transport.
- Use narrow signal/event objects for pipeline progress instead of modules
  importing each other's internals.
- Keep generated demo project templates behind the local-demo boundary.

Definition of done:

- Current dispatcher tests still pass.
- Tests can inject temp roots, fake Codex transport, and command runners without
  mutating global module variables.
- Public CLI behavior remains compatible.

### 6. Launch Desk GI Alignment

Objective: decide and document whether `launch-desk` is active product or
legacy/experimental, then make its runtime obey GI rules.

Current decision for this sprint:

- Treat `launch-desk` as a legacy/experimental app until the user decides it is
  part of the main mini-orchestrator product.

Required cleanup:

- Move or document `launch-desk` under a legacy/experimental boundary.
- Add a GI-compliant startup contract if it remains runnable:
  config-service lookup before binding, service id, guide/contract endpoints,
  no guessed fallback port for web/API runtime.
- Repair local dependency state or document install verification so backend and
  frontend checks are reproducible.

Definition of done:

- Main README no longer implies `launch-desk` is active mini-orchestrator
  runtime.
- If `launch-desk` is runnable, it has documented config-service startup rules.
- Its tests/build commands either pass after install or have a precise blocker.

## Verification Matrix

- `python -m compileall mini_orchestrator`
- `python tools\codex-dispatcher\test_dispatcher.py`
- `python -m mini_orchestrator "search AGENTS" --no-log`
- UI health and plan endpoint smoke through the config-service selected port
  when service record is available.
- Dispatcher plan-only real planner smoke when Codex app-server and selected
  model are available.
- Launch Desk backend/frontend checks after dependency restore if it remains
  runnable.

## Risks

- Splitting dispatcher can accidentally change CLI behavior. Mitigation: split
  behind existing tests and add compatibility tests before moving code.
- Real planner preview depends on Codex app-server availability and selected
  model access. Mitigation: keep explicit dry-run/demo fallback.
- Launch Desk may not be worth preserving. Mitigation: classify as legacy first,
  then only invest in GI startup if it remains useful.

## Completion Notes

Date: 2026-06-17

- Package-native search now excludes hidden/generated/noisy paths and has
  focused tests for exclusions and root boundaries.
- Package-native `run_command` uses a safe argv adapter with destructive command
  blockers, timeout handling, and focused tests.
- `/api/campaign` is removed from active UI routing; the service contract stays
  focused on core run, dispatcher plan/run, and agent mini chat.
- `/api/dispatcher/plan` supports explicit `mode: "demo"` and `mode: "real"`;
  real mode calls dispatcher `--plan-only` without `--dry-run`.
- Dispatcher now delegates models, routing, events, prompts, and command
  execution to focused modules while preserving the existing CLI/test surface.
- `launch-desk/` is documented as legacy/experimental with GI startup caveats.
  Current Launch Desk check blocker: backend/frontend `tsc.cmd` and
  `vitest.cmd` shims are missing until dependencies are restored.
