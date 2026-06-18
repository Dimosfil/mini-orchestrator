# Handoff Summary: Dental CRM Kanban smoke and visual-agent execution boundary

Date: 2026-06-18 22:56:42
Thread topic: Showing Symphony-style task-card movement in mini-orchestrator and clarifying what is not yet executed by visual agent cards

## User Intent

- Run a visible test task for a dentistry CRM.
- See a task card move through a Kanban board like the Symphony reference.
- Understand whether this required the Symphony daemon.
- Understand whether the task was executed by the visual agent card built in
  Agent Builder.
- Decide what to do next.

## Current Decision

- Symphony daemon is not required for the current visible smoke.
- The current mini-orchestrator can show task-card movement by replaying
  dispatcher JSONL events through `/api/daemon/runs`.
- This is still dispatcher observability, not the real WorkNest/Symphony daemon
  lifecycle.
- Visual agent cards are not yet executable workflow agents for dispatcher
  tasks. They currently support browser-local configuration and mini-chat, but
  not backend flow persistence, compile, and run.

## Implemented In This Thread

- Changed the main dashboard Live Runs view to render a compact Kanban board:
  - `Backlog`
  - `Todo`
  - `In Progress`
  - `Human Review`
  - `Done`
- Added run-card placement logic based on dispatcher live state:
  - planner running/planning -> `Todo`
  - executor running -> `In Progress`
  - reviewer running or approval/failed -> `Human Review`
  - done -> `Done`
  - queued -> `Backlog`
- Kept dispatcher JSONL as source of truth; UI does not invent worker progress.
- Updated `tools/project-memory/pending-tasks.md` with the completed
  Symphony-style Kanban live-run-card task.

## CRM Task Runs

- A dry-run background task was started:
  - Run id: `ui-075330990d11`
  - Task: dentistry CRM MVP cards/appointments/treatment statuses/admin tasks.
  - Result: completed almost instantly and appeared in `Done`.
- A real background dispatcher chain was then started with a safe read-only
  planning/review task:
  - Run id: `ui-b9b4096ba055`
  - Task: prepare MVP plan for dentistry CRM without editing files.
  - Observed live movement:
    - planner running -> `Todo`
    - executor running -> `In Progress`
    - reviewer running -> `Human Review`
    - workflow completed -> `Done`
  - Event log:
    `tools/codex-dispatcher/runs/ui-b9b4096ba055.jsonl`
  - Process output:
    `.mini_orchestrator/dispatcher-processes/ui-b9b4096ba055.stdout.json`

## Important Clarification

- No runnable dentistry CRM application was generated.
- The CRM run explicitly included `Do not edit files`, so it produced planning,
  executor notes, review notes, and Kanban movement only.
- The only runnable demo under `.mini_orchestrator/test-runs/` remains the older
  calculator demo:
  `.mini_orchestrator/test-runs/calculator-demo/index.html`

## Visual Agent Card Boundary

- The visible Kanban task-card movement used dispatcher roles:
  `planner -> executor -> reviewer`.
- It did not use a configured visual agent card as the executing worker.
- Current visual cards can:
  - exist in Agent Builder UI/localStorage;
  - store model, speed, reasoning, access mode, and work-package fields;
  - chat through `/api/agents/chat`;
  - act as a future worker-profile design surface.
- Missing before visual cards become executable workflow agents:
  - backend persistence for flows/cards;
  - flow validation;
  - compile to immutable worker profile snapshot;
  - run endpoint that starts a task through the selected compiled profile;
  - Live Runs mapping from run state to the selected visual card/profile.

## Verification

- `python -m pytest`
  - Result: `34 passed`.
- `python -m compileall mini_orchestrator`
  - Result: no errors.
- Inline script parse check for `mini_orchestrator/web/index.html` through Node:
  - Result: `inline scripts parse ok: 1`.
- UI health remained available at `http://127.0.0.1:8000/health`.
- Dashboard was opened at `http://127.0.0.1:8000/`.

## Current Worktree Notes

- Dirty files seen after the thread:
  - `mini_orchestrator/live_runs.py`
  - `mini_orchestrator/web/index.html`
  - `tests/test_live_runs.py`
  - `tools/project-memory/pending-tasks.md`
  - `tools/project-memory/symphony-worknest-agent-card-plan.md`
- Some of these files were already dirty before the Kanban UI change. Do not
  assume all changes belong to this latest task without inspecting diffs.

## Suggested Next Direction

- Best immediate product step:
  create a runnable dentistry CRM demo under
  `.mini_orchestrator/test-runs/dental-crm-demo/` with a static `index.html`,
  seed data, patient cards, appointments, treatment statuses, and admin-task
  Kanban.
- Best orchestration step after that:
  connect one selected visual agent card as a real executable worker profile:
  persist -> validate -> compile -> run -> show in Live Runs.
