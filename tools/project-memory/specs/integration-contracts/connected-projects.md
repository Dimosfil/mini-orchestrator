# Connected Projects

This register lists external projects, repositories, services, libraries, docs
sites, upstream tools, cloned examples, and sibling workspaces that this project
depends on, researches, vendors, or regularly interacts with.

Agents should read this file before touching integrations, nested repositories,
cloned examples, external project folders, or cross-project service contracts.
Do not treat an entry here as permission to inspect arbitrary files; follow the
project scope, privacy rules, and explicit user request.

## D:\AI\general-instructions

- Purpose: canonical shared instruction library and source of GI migrations.
- Business or architectural role: supplies project-local agent instructions,
  startup/RAG workflow rules, command contracts, and reusable migration intake
  for this repository.
- Local folder: `D:\AI\general-instructions`.
- Canonical Git/package/docs URLs:
  `https://github.com/Dimosfil/general-instructions.git`.
- Service ID or runtime endpoints: none for the checkout itself; config-service
  URL is recorded by the shared GI config when configured.
- Owner or source of truth: shared instruction source repository.
- Data/API contract: migration files under `migrations/`, copied instruction
  files under `tools/`, templates under `templates/`, and metadata in
  `tools/project-memory/instruction-kit.json`.
- Setup, sync, build, test, or update commands:
  `.\tools\check-instruction-kit-updates.ps1`; after applying file changes,
  `.\tools\check-instruction-kit-updates.ps1 -RecordApplied`.
- Version, branch, or update cadence: track accepted GI versions from
  `VERSION.md`; consume pending migrations during `gi обновить`.
- Privacy, secret, license, and access boundaries: do not copy secrets,
  private user data, generated indexes, or unrelated dirty work from the shared
  repository into this project.
- Status and caveats: active dependency for instruction-kit updates.
- Reason this dependency still exists: keeps this project aligned with shared
  agent workflow and safety rules.

## D:\AI\symphony

- Purpose: approved external reference workspace for Symphony-style
  orchestration design.
- Business or architectural role: provides design and implementation reference
  material for shaping `mini-orchestrator` orchestration concepts.
- Local folder: `D:\AI\symphony`.
- Canonical Git/package/docs URLs: not recorded yet.
- Service ID or runtime endpoints: not recorded yet.
- Owner or source of truth: local reference workspace until a canonical source
  is documented.
- Data/API contract: reference-only unless a future task defines an explicit
  integration contract.
- Setup, sync, build, test, or update commands: none approved from this project.
- Version, branch, or update cadence: not recorded yet.
- Privacy, secret, license, and access boundaries: agents may read and inspect
  this workspace for this project, but must not edit, delete, move, commit, or
  publish files there without a separate explicit user request.
- Status and caveats: approved external reference workspace.
- Reason this dependency still exists: supports Symphony-style orchestration
  research and design decisions for `mini-orchestrator`.
