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
