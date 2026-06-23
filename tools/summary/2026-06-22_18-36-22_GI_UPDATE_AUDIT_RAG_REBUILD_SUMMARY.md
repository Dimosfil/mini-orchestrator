# Handoff Summary: GI Update, Project Audit, And RAG Rebuild

## Thread Purpose

The user asked to update GI instructions, check the project against GI rules,
rebuild the GI/RAG memory layer, push the resulting changes, and write this
handoff summary.

## GI Instruction Kit State

- The project instruction kit was updated to `2026.06.21.13`.
- Applied migrations:
  - `2026.06.21.11__split_project_documentation_and_memory_layers`
  - `2026.06.21.12__abstract_concrete_examples_before_shared_rules`
  - `2026.06.21.13__modularize_agents_runtime_entrypoint`
- Root `AGENTS.md` is now a compact runtime entrypoint that routes agents to
  modules under `patterns/AGENTS_RUNTIME/`.
- New copied GI files include `CHANGELOG.md`, `INDEX.md`, `VERSION.md`,
  `patterns/AGENTS_RUNTIME/*`, several reusable patterns, and templates.
- `tools/project-memory/instruction-kit.json` records version
  `2026.06.21.13` and no pending GI migrations were found after update.

## Project Audit Findings

- The application code and tests were healthy during the audit:
  - full `python -m pytest` passed with 119 tests;
  - documented `python -m pytest tests` passed with 104 tests;
  - `tools/codex-dispatcher/test_dispatcher.py` passed with 15 tests;
  - `python -m compileall mini_orchestrator tools\codex-dispatcher
    tools\migrate_runtime_to_sqlite.py` passed;
  - `python -m mini_orchestrator "search AGENTS"` and the `--no-log` smoke path
    both completed.
- `git diff --check` had no real whitespace errors; only normal Windows LF/CRLF
  warnings appeared when files were modified.
- Important remaining GI-alignment follow-ups:
  - `tools/AGENT_RUNBOOK.md` still says the project is in bootstrap state even
    though README describes the active UI/runtime.
  - `README.md` documents `python -m pytest tests`, while the broader full
    suite is `python -m pytest`.
  - `tools/codex-dispatcher/EVENT_PROTOCOL.md` still describes chain mode as
    fixed `planner -> executor -> reviewer`, while the current runtime supports
    selected chain presets and only uses that order as the default example.
  - Campaign Concept Studio helper/config code remains in active
    `mini_orchestrator/config.py` and `mini_orchestrator/llm.py`, while project
    memory says retained campaign code should be isolated under a legacy
    boundary and not loaded as active runtime.
  - `tools/project-memory/rag-system.json` still has the placeholder
    `project_id` value `replace-with-stable-project-slug`.

## RAG Rebuild State

- The stale RAG/project-memory index found during audit was rebuilt.
- Rebuild commands completed for:
  - SQLite/FTS index via `build_project_memory_index.py rebuild`;
  - semantic chunk export via `build_project_memory_index.py export-chunks`;
  - health and retrieval evals via `rag_check.py run`.
- Current RAG health is green:
  - SQLite index readable with 198 files and 1012 chunks;
  - tracked source hashes match;
  - semantic corpus readable with 1012 chunks;
  - SQLite chunk count matches semantic corpus;
  - generated SQLite/corpus/vector paths are ignored;
  - all 4 retrieval eval cases pass.
- `tools/project-memory/retrieval-evals.json` was updated so eval expectations
  match the modular GI runtime structure after `2026.06.21.13`.
- `tools/project-memory/rag-system.json` now records `sqlite`, `chunks`, and
  `evals` as rebuilt for
  `2026.06.21.13__modularize_agents_runtime_entrypoint`.
- Vector retrieval remains disabled and was not rebuilt; this was intentionally
  a scoped node rebuild, not a full vector/manifest rebuild.

## Repository State

- The GI instruction update was committed and pushed.
- The RAG rebuild state update was committed and pushed.
- After `ги пуш`, `main` was clean and aligned with `origin/main`.

## Next Useful Work

- First low-risk batch: fix documentation drift in `tools/AGENT_RUNBOOK.md`,
  `README.md`, and `tools/codex-dispatcher/EVENT_PROTOCOL.md`.
- Next code-quality batch: decide whether to delete the old campaign helper code
  or move it behind a clearly named legacy boundary, then update project memory
  and tests accordingly.
- Optional memory cleanup: replace the placeholder `project_id` in
  `tools/project-memory/rag-system.json` with a stable project slug such as
  `mini-orchestrator`, then rebuild SQLite/chunks/evals again.

