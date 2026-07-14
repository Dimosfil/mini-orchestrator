# Architecture Migrations

Record durable architecture migration history here when project structure,
runtime boundaries, data flow, retrieval architecture, deployment shape, or
major dependencies change.

For each migration, include:

- date
- reason
- previous architecture
- new architecture
- affected files or modules
- compatibility notes
- verification performed
- rollback or follow-up notes

Keep entries concise and evidence-backed. Do not store secrets, credentials,
private user data, generated logs, or local-only runtime state.

## 2026-07-14: Canonical Executable Workflow State Machine

- Reason: CrewAI architecture research highlighted the missing runtime layer
  between Mini's already-compiled visual graph and the flat internal manifest
  dry-run order. The project needed deterministic routing and recovery without
  handing lifecycle ownership to another framework.
- Previous architecture: compiled manifests stored graph edges and bounded-loop
  metadata, but the internal runner flattened them to `executionOrder`; stage
  outputs were summary strings and state/event writes were separate.
- New architecture: `workflow_runtime.py` executes the immutable graph by
  structured `success` / `failure` outcomes, explicit conditional routes,
  bounded retries/loops/steps/runtime/context, versioned artifacts, metrics,
  and a resumable next-node pointer. SQLite checkpoints persist the run snapshot
  and transition event atomically.
- Affected files or modules: `mini_orchestrator/workflow_runtime.py`,
  `agent_flows.py`, `daemon_runs.py`, `runtime_store.py`, the service contract,
  focused tests, README, and executable-workflow project memory.
- Compatibility notes: existing linear manifests continue to run in the same
  order. The retired public daemon dry-run endpoint remains retired; approved
  Dashboard Dispatcher/Symphony product entrypoints are unchanged.
- Verification performed: package compile, the full `tests/` suite, focused
  graph/recovery tests, dispatcher tests, and `git diff --check`.
- Rollback or follow-up notes: migrate Dispatcher and Symphony node execution
  adapters incrementally to the canonical state machine. Do not restore a
  second mutable lifecycle model or add CrewAI as the task owner.

## 2026-06-21: Instruction Boundary Update For Generic Orchestration

- Reason: GI migrations `2026.06.21.2` through `2026.06.21.6` add reusable
  boundaries for developer-tool/product separation, project-agnostic shared rule
  explanations, query/prompt interpretation modules, and baseline code quality.
- Previous architecture: local instructions already contained configuration and
  RAG boundaries, and the active runtime had recently removed the default Dental
  CRM coupling in favor of a neutral Project Builder card.
- New architecture: project instructions explicitly require orchestrator and
  workflow UI behavior to treat generated products as task data/output, keep
  workflow logs tied to the selected or active run, isolate query/prompt
  interpretation behind adapters or resources, and preserve clear module and
  integration boundaries.
- Affected files or modules: `AGENTS.md`, `tools/AGENT_WORKING_AGREEMENTS.md`,
  and `tools/project-memory/instruction-kit.json`.
- Compatibility notes: historical generated artifacts and summaries may still
  mention concrete domains as examples or past runs, but they are not runtime
  defaults or normative contracts.
- Verification performed: pending GI migrations were inspected before applying
  docs changes; no application source changes were required by this update.
- Rollback or follow-up notes: if future work changes RAG source rules,
  chunking, embedding metadata, or retrieval adapters beyond instruction text,
  rebuild the affected `rag-system.json` nodes and record successful status.

## 2026-06-21: Instruction Update Surface Refactor

- Reason: `gi обновить` migrations `2026.06.21.11` through
  `2026.06.21.13` required runtime documentation changes: routing runtime
  instructions through focused modules, abstracting project-specific evidence from
  shared defaults, and separating project documentation from implementation
  behavior docs.
- Previous architecture: agent runtime guidance and copied instruction files were
  largely monolithic in `AGENTS.md` and absent some documentation-split layers.
- New architecture: runtime guidance now uses `patterns/AGENTS_RUNTIME/` modules as
  the compact runtime shape and explicit update/docs/pattern files in `patterns/`,
  `templates/`, and root docs (`INDEX.md`, `CHANGELOG.md`, `VERSION.md`).
- Affected files or modules:
  - `AGENTS.md`
  - `INDEX.md`
  - `CHANGELOG.md`
  - `VERSION.md`
  - `patterns/AGENTS_RUNTIME/*`
  - `patterns/PROJECT_DOCUMENTATION_LAYERS.md`
  - `patterns/PROJECT_MEMORY_SPECIFICATIONS.md`
  - `patterns/CONFIGURATION_BOUNDARIES.md`
  - `patterns/DEVELOPMENT_TOOL_PRODUCT_BOUNDARIES.md`
  - `templates/AGENTS.template.md`
  - `templates/AGENT_WORKING_AGREEMENTS.template.md`
  - `templates/instruction-kit.template.json`
  - `templates/rag-system.template.json`
  - `templates/TECHNOLOGY_STACK.template.md`
  - `templates/project-memory-README.template.md`
  - `tools/project-memory/instruction-kit.json`
- Compatibility notes: behavior remains project-local and implementation contracts
  stay in `tools/project-memory/` and existing README/runbook files.
- Verification performed: copied modules and template files were synchronized from the
  shared instruction source; updated `tools/project-memory/instruction-kit.json`;
  then planned migration IDs were recorded with
  `check-instruction-kit-updates.ps1 -RecordApplied`.
- Rollback or follow-up notes: no functional application behavior changed; any
  reversion should restore the monolithic `AGENTS.md` layout and copied file
  metadata if needed.
