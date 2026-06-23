# Handoff Summary: GI Summary Command

## Thread Purpose

The user invoked the Russian `gi summary` form, which maps to the local
`gi summary` command.
The command requires writing a handoff summary file under `tools/summary/`, not
only summarizing in chat.

## Loaded Local Rules

- Root `AGENTS.md` identifies this workspace as the mini-orchestrator project
  and routes GI commands through the copied instruction-kit runtime.
- `tools/AGENT_WORKING_AGREEMENTS.md` defines `gi summary` and its Russian form
  as a handoff-summary request for the current project.
- Handoff summaries should be thematic, preserve user intent, decisions,
  architecture/product context, verification evidence, blockers, and next useful
  context, and avoid routine command bookkeeping unless it affects the next
  agent's work.
- The configured project response language preference lists English as the fixed
  primary language with Russian also available.

## Current Repository State

- A previous summary file exists at
  `tools/summary/2026-06-22_18-36-22_GI_UPDATE_AUDIT_RAG_REBUILD_SUMMARY.md`.
- `git status --short` showed that previous summary file as untracked before
  this new summary was created.
- No code, runtime, or project-memory behavior changes were made for this
  command; only this handoff summary file was added.

## Latest Available Project Context

- The previous handoff says the GI instruction kit was updated to
  `2026.06.21.13`.
- It records successful verification for the application and GI/RAG layer,
  including Python tests, compile checks, smoke checks, SQLite/chunk rebuilds,
  and retrieval evals.
- It also records remaining follow-ups:
  - update drift in `tools/AGENT_RUNBOOK.md`, `README.md`, and
    `tools/codex-dispatcher/EVENT_PROTOCOL.md`;
  - decide how to isolate or remove old Campaign Concept Studio helper code in
    active runtime modules;
  - replace the placeholder `project_id` in
    `tools/project-memory/rag-system.json` with a stable project slug and
    rebuild affected RAG nodes afterward.

## Next Useful Context

- If the next user request is another GI command, keep it scoped to this current
  project root and do not resume older product work unless explicitly asked.
- If the user asks to commit or push, inspect status first and include only
  scoped summary files or requested changes, preserving unrelated/user changes.
