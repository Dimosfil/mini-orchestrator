# Handoff Summary: Symphony demo and WorkNest mapping

Date: 2026-06-21 17:13:06

## Topic

The thread compared OpenAI's Vimeo `Symphony Demo` with the current
Mini Orchestrator implementation and clarified how to map the demo's product
surface to this project.

## External Demo Understanding

- The Vimeo video is `Symphony Demo` by OpenAI, duration 43 seconds.
- The visible `todos` application in the demo is not the orchestration system
  itself. It is a simple product surface where the user asks for a change, such
  as adding counters/badges for `Active` and `Completed`.
- The orchestration layer then turns that product request into tracked work,
  moves it through agent execution, human review, merge/done states, and the
  product surface reflects the finished change.

## Current Mini Orchestrator Shape

- Mini Orchestrator already has the orchestration/control layer:
  - Dashboard and Live Runs.
  - Dispatcher and Symphony execution modes.
  - Selectable agent chain presets.
  - One visible task card per executing chain.
  - Planner/Executor/Reviewer-style stages as the default example, not a fixed
    workflow.
  - Human Review with `ToDone` and `Доработки`.
- Dispatcher mode runs the selected chain locally through Codex app-server and
  stores runtime state in `.mini_orchestrator/runtime.sqlite3`.
- Symphony mode builds `mini-orchestrator.symphony-intake.v1` payloads with
  one `agentTasks[]` item per selected preset agent and submits only through a
  config-service-resolved, documented Symphony intake contract.
- If Symphony intake is missing or unavailable, Mini records a visible blocked
  gateway run instead of pretending the task was accepted.

## Important Mapping Decision

- The user clarified that in this project, the demo's `todos` product surface
  should map to **WorkNest**.
- In other words:
  - `todos` in the video = the user-facing task/product source.
  - WorkNest in Mini Orchestrator = the task source and terminal completion
    sink.
  - Mini Orchestrator = the orchestration dashboard and agent-chain execution
    layer.
  - Symphony = an optional/external execution or observability backend when its
    contract is available.

## Product Implication

- Future comparisons to the Symphony demo should not assume Mini needs a new
  standalone todo app just to match the metaphor.
- The closer target is a WorkNest-centered loop:
  1. WorkNest task is claimed or selected through documented manager contract.
  2. Mini Orchestrator runs the approved task through the selected chain.
  3. Live Runs shows progress and Human Review.
  4. User accepts with `ToDone` or requests `Доработки`.
  5. Terminal completion is reported back to WorkNest only through documented
     contract operations.

## Caveats

- WorkNest remains the source of truth for sprint/task lifecycle.
- Mini must not read WorkNest storage directly or move arbitrary WorkNest
  states unless the manager contract documents that capability.
- Existing project docs note that WorkNest terminal `done` requires explicit
  user acceptance.
