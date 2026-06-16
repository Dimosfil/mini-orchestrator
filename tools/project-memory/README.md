# Project Memory

This folder stores durable project knowledge for AI agents.

Use it for verified findings that should survive chat resets:

- architecture notes
- debugging findings
- important decisions
- known pitfalls
- local workflows
- dependency maps
- reusable agent experience that may improve `gi`

Do not store secrets or credentials here.

## Reusable Experience For GI

When this project reveals a reusable workflow, failure pattern, token-saving
tactic, or agent-instruction improvement, write a concise recommendation for the
shared instruction kit.

Prefer the `updates/` folder in an available checkout/cache of the canonical
shared-instruction source repo when this repository is being maintained:

```text
<general-instructions checkout>\updates\
```

If the shared library is unavailable, use a local intake folder:

```text
tools/project-memory/instruction-updates/
```

Recommendations should include:

- observed problem or repeated friction
- reusable rule, pattern, template, checklist, or migration idea
- evidence paths or commands
- expected benefit for token economy, startup retrieval, safety, or workflow
- privacy review notes

Do not include secrets, credentials, private user data, production data, or
unnecessary project-specific details.

## Agent Memory SQLite

If the project benefits from searchable agent memory, use a local SQLite
database as an agent index/experience store, not as the application database.

Recommended path:

```text
tools/project-memory/project_memory.sqlite
```

The SQLite file is usually local/generated and ignored by git when it is large
or rebuildable. Commit the indexing script, schema notes, and Markdown exports
instead.

Use the database for verified facts, searchable file/symbol indexes, debugging
findings, useful commands, recurring failures, and durable notes with evidence
paths. Do not store secrets, credentials, private user data, or production data.

Do not dump the database into chat. Query it by symbol, path, topic, error, or
feature name with small limits.

## Two Memory Layers

- Markdown is the human-reviewable layer. Keep summaries, decisions,
  architecture notes, and curated exports concise.
- SQLite is the searchable agent-memory layer for detailed findings,
  file/symbol indexes, references, commands, failures, and evidence-backed notes.

Do not blindly migrate all Markdown into SQLite. When Markdown memory becomes
too large to read cheaply, introduce or rebuild the SQLite memory/index and keep
Markdown as the concise reviewable export.

## RAG System Structure

When the project needs retrieval that can grow beyond Markdown and SQLite FTS,
add:

```text
tools/project-memory/rag-system.json
```

Use `templates/rag-system.template.json` as the starter shape and
`patterns/RAG_SYSTEM_STRUCTURE.md` as the architecture rule. Keep vector stores
such as Chroma, Qdrant, and pgvector behind retrieval adapters so prompts and
agent workflows do not depend on one storage backend.

Before enabling vector retrieval, prepare semantic-ready chunks and embedding
metadata with `patterns/SEMANTIC_RAG_RETRIEVAL.md`. Keep generated files such as
`tools/project-memory/semantic-corpus.jsonl` ignored.

For a local semantic MVP, build Chroma from exported chunks:

```powershell
python .\tools\project-memory\build_project_memory_index.py rebuild
python .\tools\project-memory\build_project_memory_index.py export-chunks
uv run --with chromadb python .\tools\project-memory\build_chroma_index.py rebuild
```

## Suggested Files

- `pending-tasks.md`: active project-wide plans and multi-step work.
- `STUDY_PLAN.md`: roadmap for understanding the project.
- `git-preferences.json`: commit-message language preferences.
- `system-preferences.json`: agent user-facing working language preferences.
- `rag-system.json`: RAG source, exclusion, retrieval, context-packet, and
  writeback configuration.
- `semantic-retrieval-evals.md`: small eval set for semantic and hybrid
  retrieval quality.
- `build_chroma_index.py`: optional local Chroma adapter when semantic
  retrieval is enabled.
- `NOTES.md`: reviewable export of durable notes from local agent memory.
- `architecture.md`: verified architecture notes.
- `decisions.md`: durable decisions and rationale.
- `known-issues.md`: recurring bugs, caveats, and workarounds.

## Task Planning

For analysis, refactoring, migration, or multi-step implementation tasks, keep a
concise checklist in `pending-tasks.md` or a dedicated task plan in this folder.

Include:

- goal
- planned changes
- execution order
- risks or dependencies
- verification steps

Update progress as meaningful steps complete. Keep plans task-relevant and avoid
full diffs, large logs, generated outputs, secrets, credentials, or private
production data.

## Rule

If a future agent would waste time rediscovering the same fact, write it down.
