# User Review Gate

## Purpose

Agent completion is not the same as user acceptance. A finished agent task must
land in a review state where the user decides whether the result is complete or
needs another pass.

## Workflow Contract

- During execution, the Kanban board shows one task card in `In Progress` for
  the whole configured agent chain. It must not split one user task into
  separate Kanban task cards per agent.
- The task card must expose `currentAgent`, meaning the visual card or worker
  currently handling the task.
- The task card should also show the configured stage/agent chain so the user
  can see progress through the agents selected in Agent Builder.
- When an agent returns a ready result, show it in user review instead of moving
  it directly to final Done.
- The review card must expose two user choices:
  - `ToDone`: the user accepts the result and the task moves to final Done.
  - `Доработки`: the user rejects or partially accepts the result and the task
    remains in review/rework flow.
- The result summary, artifact paths, event log, and generated output must stay
  visible while the task is in review.
- Future task-manager or daemon integration should persist this decision in the
  authoritative task state. Until that endpoint exists, UI-only review choices
  may be stored locally but must be treated as a temporary client-side bridge.

## Current Implementation Map

- Agent instruction rule: `AGENTS.md`
- Dashboard bridge: `mini_orchestrator/web/index.html`
- Current bridge storage: browser `localStorage` key
  `mini-orchestrator-run-review-decisions-v1`
