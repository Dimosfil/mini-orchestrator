# Handoff Summary: Symphony-style prototype orientation

Date: 2026-06-18 19:20:31
Thread topic: Clarify what OpenAI Symphony is, approve local Symphony reference
workspace access, and assess whether mini-orchestrator already has a service or
daemon layer.

## User Intent

- The user says the system is "more or less ready" and wants to create the first
  orchestrator prototype based on Symphony.
- The user is still clarifying the mental model:
  - whether Symphony is just a Markdown file;
  - whether it is a service/daemon;
  - which equivalent parts already exist in this project.
- Treat next Symphony work as practical prototype work, not only research.

## Symphony Understanding Established In Chat

- Symphony is best understood as a specification plus a runnable service/daemon
  pattern.
- Markdown files define the operating contract:
  - a spec or architecture file describes the orchestration model;
  - a workflow file such as `WORKFLOW.md` tells agents how to work in a target
    repo.
- The service/daemon is the process that executes the control loop:
  - polls or receives tasks;
  - claims a task;
  - creates or chooses a workspace/run context;
  - launches Codex through app-server;
  - tracks state and logs;
  - handles retry, continuation, blocked, review, and done outcomes.
- The key distinction for this project:
  - Markdown is the contract and policy layer.
  - The daemon/controller is the lifecycle executor.

## Approved External Reference Workspace

- The user explicitly approved using:
  - `D:\AI\symphony\`
- This was recorded as a narrow project rule in:
  - `AGENTS.md`
  - `tools/AGENT_WORKING_AGREEMENTS.md`
- New rule meaning:
  - agents may read, search, inspect, and use `D:\AI\symphony\` when designing
    or implementing Symphony-style orchestration in `mini-orchestrator`;
  - agents must not edit, delete, move, or commit files in that external
    workspace unless the user gives a separate explicit action for that path.
- These rule edits are currently uncommitted at the time of this summary.

## Current Project State Assessed

- The project already has parts of the execution/service layer:
  - `python -m mini_orchestrator --ui` starts a long-running HTTP UI service.
  - `mini_orchestrator/ui.py` owns the threaded HTTP server and API endpoints.
  - `mini_orchestrator/codex_dispatcher_service.py` owns
    `PersistentCodexDispatcher`, which lives inside the UI process and reuses
    Codex app-server and some Codex threads.
  - `tools/codex-dispatcher/codex_app.py` wraps `codex app-server` as a
    subprocess and communicates with it programmatically.
- The project does not yet have a Symphony-style daemon/control plane:
  - no durable local run queue;
  - no task claiming or lease lifecycle;
  - no persistent state machine for `queued`, `claimed`, `running`,
    `needs_review`, `blocked`, `failed`, `done`;
  - no retry/backoff or crash recovery for runs;
  - no controller that owns multiple runs independently of a single UI request.

## Important Git State

- Earlier in this thread, `gi push` succeeded:
  - commit `43f050a Add dispatcher worker tech summary`;
  - pushed `main` to `origin/main`;
  - tests before that push: `python -m pytest` -> 30 passed.
- Current working tree after the permission/rule update:
  - modified `AGENTS.md`;
  - modified `tools/AGENT_WORKING_AGREEMENTS.md`;
  - this summary file is newly added by `gi summary`.
- No commit was made for the rule update or this summary unless a later turn
  does it.

## Suggested Next Implementation Direction

- Build the first local Symphony-style prototype as a small control plane
  beside the current UI/dispatcher, not as a wholesale copy of Symphony.
- Likely Phase 1:
  - inspect `D:\AI\symphony\` for the minimal spec/service concepts to adapt;
  - create `ORCHESTRATOR_WORKFLOW.md` or `WORKFLOW.md` for this project;
  - add a local run model and durable run store;
  - expose basic API endpoints to create, inspect, and advance runs;
  - connect one run execution path to the existing dispatcher/Codex app-server.
- Keep the current UI, visual agent mini-chat, translation helper, and dispatcher
  behavior intact while adding the new lifecycle layer.

## Continuation Point

- If the user says to start the prototype, first read targeted files:
  - `D:\AI\symphony\` relevant spec/service entrypoints;
  - `mini_orchestrator/ui.py`;
  - `mini_orchestrator/codex_dispatcher_service.py`;
  - `tools/codex-dispatcher/codex_app.py`;
  - `tools/project-memory/dispatcher-codex-optimization.md`;
  - `tools/project-memory/codex-native-orchestrator-plan.md`;
  - `tools/project-memory/pending-tasks.md`.
- Then write or update a concise project-memory implementation plan before
  editing code, per project rules for non-trivial architecture work.
