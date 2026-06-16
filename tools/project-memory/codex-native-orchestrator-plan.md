# Codex-native Orchestrator Plan

Date: 2026-06-16

## Goal

Build the mini-orchestrator around Codex-native execution rather than a generic
OpenAI Agents SDK worker pool. The target workflow is a dispatcher that can
coordinate multiple Codex agents with different models, collect their results,
and pass summaries between them.

## Recommended Architecture

Use Codex custom agents for the human-facing/native workflow, then add a
programmatic dispatcher using Codex SDK or Codex app-server when the protocol
needs to be controlled by application code.

Initial agent roles:

- `planner`: turns rough user requests into scoped execution plans, risks, and
  handoff contracts.
- `executor`: performs bounded implementation or technical steps.
- `reviewer`: checks correctness, regressions, missing tests, and unresolved
  assumptions.
- `dispatcher`: owns routing, summarization, retry decisions, and final
  response assembly.

## MVP Flow

1. User gives a task to the dispatcher.
2. Dispatcher asks planner for a plan.
3. Dispatcher sends the accepted plan or a bounded task to executor.
4. Dispatcher sends executor output to reviewer.
5. Dispatcher decides whether to finish, retry, ask the user, or create follow-up
   work.
6. Each handoff is recorded as a compact event for replay and debugging.

## Implementation Steps

1. Add `.codex/agents/planner.toml`, `.codex/agents/executor.toml`, and
   `.codex/agents/reviewer.toml`.
2. Add a project-local dispatcher prototype under `tools/codex-dispatcher/`.
3. Prefer Codex SDK/app-server for real thread orchestration and streaming
   events.
4. Persist run events as JSONL under a project-local runtime folder that remains
   ignored when it contains generated logs.
5. Integrate WorkNest only as the task queue/lifecycle recorder. WorkNest does
   not execute agent work.

## Current Local Decisions

- Task manager service: `worknest`.
- Config-service URL: `http://127.0.0.1:4100`.
- WorkNest agent API: `http://127.0.0.1:4187/agent-intake`.

## Open Questions

- Which exact Codex models should be pinned per custom agent?
- Should dispatcher execution be Python-first to match this repo, or
  TypeScript-first to use the Codex TypeScript SDK?
- Which run artifacts should be durable project memory versus generated runtime
  logs?
