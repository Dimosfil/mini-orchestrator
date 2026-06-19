# Handoff Summary: Symphony daemon, visual-agent chains, and WorkNest sprint

Date: 2026-06-19 00:02:37
Thread topic: Clarifying how Symphony can control visual agent cards and adding a WorkNest sprint for executable card-chain daemon work

## User Intent

- Find and start the Symphony daemon/service if it exists locally.
- Understand whether Symphony can receive data from mini-orchestrator visual
  agent cards.
- Understand what happens when the user has a chain of three agents rather
  than one card.
- Turn the resulting implementation plan into a WorkNest sprint via `gi add
  sprint`.

## Symphony Runtime Status

- The registered Symphony project/service is:
  `D:\AI\symphony\elixir`.
- Config-service has a `symphony` service record:
  - base URL: `http://127.0.0.1:4000`
  - state endpoint: `http://127.0.0.1:4000/api/v1/state`
  - startup cwd: `D:/AI/symphony/elixir`
  - startup command:
    `mise exec -- escript bin/symphony WORKFLOW.md --port 4000 --i-understand-that-this-will-be-running-without-the-usual-guardrails`
- The service was already running, so no duplicate process was started.
- Verification evidence:
  - `GET http://127.0.0.1:4000/api/v1/state` returned healthy state.
  - Counts were empty at the time: `running=0`, `blocked=0`, `retrying=0`.
  - Port `4000` was owned by `erl.exe`, PID `12960`.
  - Dashboard root `http://127.0.0.1:4000/` returned HTTP 200.

## Design Clarification

- Symphony should not execute browser `localStorage` visual cards directly.
- A visual card is design state. It becomes executable only after backend
  persistence, validation, and compile.
- The execution contract should be:
  `visual card/flow -> saved backend flow -> validated flow -> immutable worker
  profile snapshot/run manifest -> daemon runner`.
- For a single card, the daemon consumes one compiled worker profile snapshot.
- For a three-agent chain such as `Planner -> Executor -> Reviewer`, the daemon
  needs a flow manifest and runner:
  - identify the start node;
  - run Planner;
  - save Planner output as a structured artifact;
  - pass that artifact to Executor;
  - save Executor output as a structured artifact;
  - pass task context plus artifacts to Reviewer;
  - map Reviewer verdict to `done`, `needs_changes`, `blocked`, or `failed`.
- Previous agent outputs should be passed as compact structured artifacts, not
  full chat logs.

## Current Boundary

- The current external Symphony reference provides the useful daemon pattern:
  long-running lifecycle, Codex app-server workers, dashboard/API state, and
  orchestration-service behavior.
- It does not currently understand mini-orchestrator visual cards as named
  Planner/Executor/Reviewer profiles.
- Current mini-orchestrator already has:
  - dispatcher chain roles `planner -> executor -> reviewer`;
  - Live Runs backed by dispatcher JSONL and/or daemon state bridge;
  - visual agent cards and mini-chat;
  - access/model/reasoning fields in card UI.
- Missing before visual cards become executable workflow agents:
  - backend flow persistence;
  - server-side flow validation;
  - compile into immutable worker profile snapshots;
  - approval/run manifest UI;
  - daemon runner for one card, then multi-card graph execution;
  - per-node Live Runs state;
  - WorkNest lifecycle bridge through documented API.

## WorkNest Sprint Added

- User command: `ги адд спринт`.
- WorkNest was resolved through config-service using project-local
  `tools/project-memory/task-manager.json` with `service_id=worknest`.
- Live WorkNest service record:
  - API: `http://127.0.0.1:4187/agent-intake`
  - contract: `http://127.0.0.1:4187/agent-intake/contract`
- Contract was read before the state-changing request.
- Sprint was created via:
  `POST /agent-intake/raw`
- Payload used `type=plan`, because prior project evidence showed that this
  creates visible active/queued sprints, while `type=sprint` may only store a
  raw receipt.
- WorkNest response:
  - intake id:
    `2026-06-18T21-01-34-940Z_codex_ebac0eff-b443-4549-9604-d4b944abe16c`
  - status: `ready`
  - sprint id:
    `2026-06-19_00-01-34_visual-agent-chain-daemon-execution-sprint`
  - sprint status: `active`
  - sprint path:
    `projects/mini-orchestrator/sprints/2026-06-19_00-01-34_visual-agent-chain-daemon-execution-sprint`

## Sprint Tasks

1. `Хранение flow на backend / Backend flow storage`
2. `Валидация flow / Flow validation`
3. `Компиляция worker-профилей / Compile worker profiles`
4. `UI подтверждения запуска / Approval and run manifest UI`
5. `Daemon MVP для одной карточки / Single-card daemon MVP`
6. `Runner цепочки из трёх агентов / Three-agent flow runner`
7. `Live state по узлам / Per-node live state`
8. `Связка lifecycle с WorkNest / WorkNest lifecycle bridge`

## Important Operating Notes

- Do not use `/agent-intake/next-task` for passive inspection; it can claim and
  start a task.
- Use WorkNest through config-service and documented contract endpoints.
- Do not read or edit WorkNest storage directly unless the user gives a
  specific path/action and local rules allow it.
- The external `D:\AI\symphony` checkout remains reference/runtime scope for
  this discussion, but do not edit it without explicit user approval.
- If implementing the sprint, start with backend flow persistence and
  validation before daemon execution.

