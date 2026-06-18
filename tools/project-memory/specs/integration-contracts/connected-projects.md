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
- Canonical Git/package/docs URLs:
  `https://github.com/openai/symphony.git`.
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

## D:\AI\LaunchDeskOpenAI

- Purpose: sibling OpenAI Agents SDK application for turning launch ideas into
  actionable release plans.
- Business or architectural role: useful reference for a full-stack
  OpenAI-backed agent app with React/Vite frontend, Express API, SSE streaming,
  deterministic tools, and validation docs.
- Local folder: `D:\AI\LaunchDeskOpenAI`.
- Canonical Git/package/docs URLs:
  `https://github.com/Dimosfil/LaunchDeskOpenAI.git`.
- Service ID or runtime endpoints: README records local frontend
  `http://127.0.0.1:5173` and backend health
  `http://127.0.0.1:8787/api/health`; resolve through GI config-service when
  using it as a running local service.
- Owner or source of truth: local checkout and GitHub repository.
- Data/API contract: project-local README, docs, `src/shared` schemas,
  `src/server` routes, and `src/agent` instructions define behavior.
- Setup, sync, build, test, or update commands: README records `npm install`
  and `npm run dev`; tests and stream verification live under `tests/` and
  `scripts/`.
- Version, branch, or update cadence: not recorded yet.
- Privacy, secret, license, and access boundaries: may require
  `OPENAI_API_KEY`; do not copy keys, local env files, generated build output,
  or dependency folders into this project.
- Status and caveats: connected sibling project; inspect only when a task
  explicitly needs Launch Desk context or integration.
- Reason this dependency still exists: provides a concrete OpenAI agent app
  reference for mini-orchestrator UI, streaming, and agent workflow decisions.

## D:\AI\WorkNest

- Purpose: personal planning system for tasks, ideas, projects, decisions, and
  AI-agent assignments.
- Business or architectural role: task-management and project-memory reference
  for workflows that convert loose ideas into structured tasks and projects.
- Local folder: `D:\AI\WorkNest`.
- Canonical Git/package/docs URLs:
  `https://github.com/Dimosfil/WorkNest.git`.
- Service ID or runtime endpoints: not recorded here; resolve through
  config-service and the WorkNest guide or contract before using any running
  service.
- Owner or source of truth: local checkout and GitHub repository.
- Data/API contract: WorkNest README, `AGENTS.md`, `COMMANDS.md`, project
  folders under `projects/`, and any service guide or contract endpoints when
  available.
- Setup, sync, build, test, or update commands: not recorded in this register;
  read WorkNest project-local docs before running commands.
- Version, branch, or update cadence: not recorded yet.
- Privacy, secret, license, and access boundaries: contains task-manager data
  and at least one local credential-shaped file in the checkout; do not read,
  copy, commit, or summarize secrets, private task data, raw storage, or
  personal records unless the user gives a specific path and action.
- Status and caveats: connected sibling task-management project; not a generic
  filesystem fallback for mini-orchestrator.
- Reason this dependency still exists: provides the likely task-manager and
  durable planning reference for GI-style project workflows.

## D:\AI\AiAnalytics\token-lens

- Purpose: local analytics application for token-usage inspection across agent
  runs and model calls.
- Business or architectural role: reference for cost, usage, and token
  telemetry workflows that may inform mini-orchestrator reporting.
- Local folder: `D:\AI\AiAnalytics\token-lens`.
- Canonical Git/package/docs URLs:
  `https://github.com/Dimosfil/token_lens.git`.
- Service ID or runtime endpoints: README records local app
  `http://127.0.0.1:8765`; resolve through GI config-service before treating it
  as a discoverable service.
- Owner or source of truth: local checkout and GitHub repository.
- Data/API contract: imports usage metadata into `data\analytics.sqlite` from
  read-only Codex log sources; README states prompts, responses, tool payloads,
  raw logs, and secrets are not stored in the analytics database.
- Setup, sync, build, test, or update commands: README records `.\start.ps1`
  and `.\stop.ps1`; read project-local docs before running them.
- Version, branch, or update cadence: not recorded yet.
- Privacy, secret, license, and access boundaries: treat Codex logs, analytics
  databases, local config, and generated data as private; inspect only the
  specific files required for a user-approved analytics task.
- Status and caveats: connected sibling analytics project; current README text
  appears to be stored or displayed with non-UTF-8/mojibake in this shell, so
  preserve encoding carefully when editing that project.
- Reason this dependency still exists: provides a local token-accounting
  reference for future mini-orchestrator cost and usage reporting.
