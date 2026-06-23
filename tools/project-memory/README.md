# Project Memory

This folder stores concise, implementation-driving project knowledge for AI
agents.

Use Markdown and JSON files here for human-reviewable memory. Use the local
SQLite database only as a generated search index that can be rebuilt from git
tracked files.

## Documentation Versus Summary Versus Project Memory

`README.md`, `docs/`, and runbooks are project documentation: overview,
functionality, stack, commands, operations, troubleshooting, and examples.
`tools/summary/` is compact handoff state for the current or recent chat.
`tools/project-memory/` is long-lived implementation-driving knowledge:
algorithms, business rules, workflow contracts, state machines, invariants,
architecture decisions, and verification guarantees.

Do not store raw work results, generated product outputs, screenshots, photos,
crawled/downloaded files, large logs, model outputs, build artifacts, export
bundles, or run datasets in this folder. Put those files in a project-local
artifact, evidence, output, data, or docs-asset location and keep only compact
summaries, manifests, checksums, or links here when they are needed for a
decision, behavior contract, failure, or verification result.

Write project-memory documents so another agent could rebuild the project on a
different language, framework, platform, or UI stack and preserve the same
behavior. Code is the current implementation; project-memory specifications are
the portable behavioral source of truth.

Recommended specification structure:

```text
tools/project-memory/
  architecture-migrations.md
  specs/
    features/
    business-rules/
    data-model/
    integration-contracts/
      connected-projects.md
```

Split documents by meaning. Keep feature algorithms, business logic,
architecture contracts, and implementation mapping searchable as separate
focused files instead of one giant document. Keep user-facing functionality,
stack, commands, and operations in project documentation unless a compatibility
path is explicitly linked.

Keep a connected-projects register when this project depends on, researches,
vendors, or regularly interacts with external repositories, cloned examples,
service projects, libraries, docs sites, upstream tools, or sibling workspaces:

```text
tools/project-memory/specs/integration-contracts/connected-projects.md
```

For each connected project, record its purpose, business or architectural role,
local folder when applicable, canonical Git/package/docs URLs, service IDs or
runtime endpoints, owner/source of truth, data or API contract, setup/update
commands, privacy and access boundaries, status, caveats, and why this project
needs it. Agents should read the register before touching integrations or
external project folders, and update it when a connected project is added,
removed, moved, replaced, or given a new role.

## SQLite Index

Recommended local database:

```text
tools/project-memory/project_memory.sqlite
```

Rebuild it from git tracked repository content:

```powershell
python .\tools\project-memory\build_project_memory_index.py rebuild
```

Check index size:

```powershell
python .\tools\project-memory\build_project_memory_index.py stats
```

Search indexed content:

```powershell
python .\tools\project-memory\build_project_memory_index.py search "gi config"
```

Export semantic-ready chunks for a future embedding adapter:

```powershell
python .\tools\project-memory\build_project_memory_index.py export-chunks
```

Build a local Chroma vector index from the exported chunks:

```powershell
uv run --with chromadb python .\tools\project-memory\build_chroma_index.py rebuild
```

Run semantic search through Chroma:

```powershell
uv run --with chromadb python .\tools\project-memory\build_chroma_index.py query "semantic startup retrieval"
```

Run local RAG health checks and retrieval evals:

```powershell
uv run --with chromadb python .\tools\project-memory\rag_check.py run
```

The check verifies that `rag-system.json` is readable, generated indexes are
ignored, SQLite chunks match the semantic corpus, Chroma records match the
semantic corpus when vector retrieval is enabled, and the reviewable eval cases
in `retrieval-evals.json` return at least one expected source in the configured
top results.

The database is ignored by git. Commit this README, durable Markdown notes,
preference JSON files, and indexing scripts instead.

Use SQLite for deterministic project facts and graphs: paths, symbols, exact
references, generated identifiers, asset links, reverse dependencies, commands,
failures, and evidence-backed notes. In Unity-like projects, this can include
`.meta` GUID mappings, prefab/scene/material/script references, and
assembly-definition dependencies.

Keep logical separation between code memory and specification memory. Code
memory tracks current implementation facts such as files, symbols, commands,
schemas, and errors. Specification memory tracks product behavior, business
rules, feature algorithms, workflow contracts, architecture migrations, and
verification guarantees. Small projects may use one SQLite database with source
metadata. Larger projects should split code and spec indexes into separate
databases, schemas, collections, or source groups.

Use vector retrieval only as a second semantic layer for conceptual questions
over curated notes, summaries, architecture docs, and selected chunks. Do not
replace exact graph queries with embeddings, and always verify current source
files before editing because generated indexes can be stale.

## RAG System Structure

This repository records its expandable RAG configuration in:

```text
tools/project-memory/rag-system.json
```

The current mode is SQLite FTS. Chroma, Qdrant, pgvector, or other vector stores
should be added as retrieval adapters behind the same structure rather than as a
replacement for project memory.

Generated semantic exports such as `tools/project-memory/semantic-corpus.jsonl`
are ignored and should be rebuilt from tracked source files.

The generated Chroma index under `tools/project-memory/vector-index/chroma` is
ignored and can be rebuilt from `semantic-corpus.jsonl`.

## Activation Limits And Diagnostics

Start with Markdown specifications and targeted search. Use generated databases
when size or retrieval failures justify them.

Default SQLite/FTS activation limits:

- tracked text sources exceed 50 files;
- project-memory Markdown/JSON exceeds 25 files or about 200 KB;
- feature specifications exceed 10 files;
- exact retrieval repeatedly misses paths, commands, symbols, or feature specs;
- startup restore needs too many focused file reads.

Default vector activation limits:

- semantic-ready chunks exceed 300;
- curated project-memory specs exceed about 500 KB;
- feature specifications exceed 25 files;
- conceptual retrieval misses relevant memory at least three times;
- multiple agents need conceptual lookup over the same memory.

Use `gi sql` to inspect SQLite/FTS readiness and metrics. The agent should read
`rag-system.json`, run the local stats helper when available, count memory/spec
files, compare them with limits, and report whether SQL indexing is absent,
current, stale, or recommended.

Use `gi vector` to inspect vector readiness and metrics. The agent should read
embedding/vector metadata, check semantic corpus size and chunk count, run the
vector adapter status helper when available, and report collection, record
count, index path, freshness caveats, and readiness.

Use `gi tools rebuild evals` or `gi rag rebuild evals` to run the configured
RAG checks without rebuilding source indexes. A failing eval means retrieval may
still be structurally present but not yet trustworthy for that kind of question.
