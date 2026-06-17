# Handoff Summary: GI Refactor Sprint Planning

Date: 2026-06-17 14:36:55
Thread topic: GI-guided refactor audit, battle plan, and WorkNest sprint intake

## User Request

- The user asked to turn the refactor audit into an executable battle plan.
- Requested sequence:
  - do items 1-2 in order;
  - split dispatcher into meaningful modules with low coupling, possibly DI and signals;
  - move Launch Desk to legacy;
  - make UI plan preview use a real planner worker;
  - make Launch Desk obey GI rules if retained;
  - run `gi add sprint`.

## Local Changes

- Added `tools/project-memory/refactor-battle-plan-2026-06-17.md`.
- Updated `tools/project-memory/pending-tasks.md` with a `GI Refactor Sprint`
  checklist.

## Refactor Plan

1. Core tool guardrails:
   - exclude generated/noisy files from package-native search;
   - add path-boundary tests;
   - verify `python -m mini_orchestrator "search AGENTS" --no-log` no longer
     returns `.git`, `__pycache__`, or lockfile noise.
2. Safe command adapter:
   - move command execution policy out of ad hoc `shell=True`;
   - centralize timeout/output limits and Windows command blockers.
3. Product surface cleanup:
   - move stale Campaign Concept Studio API/code out of active UI/API.
4. Real planner worker:
   - make `/api/dispatcher/plan` capable of calling dispatcher `--plan-only`
     without `--dry-run`;
   - keep demo/dry-run mode explicit.
5. Dispatcher split:
   - target modules: models, routing, events, codex app transport, prompts,
     local demo, WorkNest client, pipeline, CLI;
   - use dependency injection for roots, runs dir, workers, command runner, and
     Codex transport;
   - use narrow signal/event objects for pipeline progress.
6. Launch Desk GI legacy:
   - classify as legacy/experimental unless promoted;
   - if runnable, add config-service startup contract and guide/contract
     endpoints.

## WorkNest Sprint

Initial mistake:

- Sent `/agent-intake/raw` payload with `type=sprint`.
- WorkNest returned `status=stored`, but no visible sprint was created.

Corrected:

- Sent the same plan again with `type=plan`.
- WorkNest returned `status=ready`, `sprintStatus=active`.
- Intake id:
  `2026-06-17T11-35-58-013Z_codex_ceddd5f1-1dbf-408d-aac5-20d0e4f1c126`.
- Sprint id:
  `2026-06-17_14-35-58_gi-refactor-sprint-...`.
- Six tasks were created in WorkNest, matching the six refactor plan items.

## Checks/Observations From Audit

- Python baseline passed:
  - `python -m compileall mini_orchestrator`
  - `python tools\codex-dispatcher\test_dispatcher.py`
  - `python -m mini_orchestrator "search AGENTS" --no-log`
- The search smoke passed functionally but exposed noisy results from `.git`,
  `__pycache__`, and lockfiles.
- Launch Desk local dependency state is incomplete:
  - `node_modules` exists, but `.bin/tsc` and `.bin/vitest` are missing;
  - backend/frontend checks failed because `tsc`/`vitest` are not recognized.

## Current Git State

- Modified:
  - `tools/project-memory/pending-tasks.md`
- Untracked:
  - `tools/project-memory/refactor-battle-plan-2026-06-17.md`
  - `tools/summary/2026-06-17_14-19-56_ORCHESTRATOR_UI_RUNTIME_IDENTITY_SUMMARY.md`
  - this summary file

## Recommended Next Step

Start with WorkNest task 1 / local plan item 1:

- harden `mini_orchestrator.tools.ToolRuntime._search`;
- add focused tests for search exclusions and path boundaries;
- run the Python verification matrix.

