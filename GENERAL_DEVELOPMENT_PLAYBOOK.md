# General Development Playbook

This is a reusable must-have plan for starting and maintaining a project with an
AI agent. Keep it short, explicit, and local to the repository.

The copied `general-instructions` kit is primarily a token-economy and
RAG-startup layer for each project. Its short command prefix is always `gi`,
not `GAI` or another alias. Use it to restore only task-relevant context from
local instructions, summaries, targeted searches, accepted migrations, and
project memory instead of broad repository reads or large outputs.

## 1. Create The Agent Entry Point

Add `AGENTS.md` in the repository root.

It should contain:

- What the project is.
- How to restore context.
- Permission for the agent to ask concise implementation questions and propose
  better-fit workflows, stacks, algorithms, or tradeoffs when useful.
- Where durable memory lives.
- How to run, test, build, and inspect logs.
- What files/folders are safe working areas.
- Rules about git, commits, generated files, secrets, and destructive commands.
- Configuration boundary rules: do not hard-code deploy, user, runtime,
  machine, service, credential, filesystem, feature-flag, or operational-policy
  values in application logic; keep them in documented project-local config,
  environment variables, or service discovery, and validate config-derived paths
  as absolute paths at startup or I/O boundaries. For search, ranking,
  retrieval, and model-facing features, treat intent interpretation,
  translation, synonym handling, prompt templates, query expansion rules,
  scoring thresholds, and model-specific normalization as configurable
  resources, dedicated modules, pipeline components, or provider-swappable
  adapters, not inline application logic.
- Development-tool/product boundary rules: orchestrators, task managers, agent
  harnesses, generators, and scaffolding systems must not bind themselves to one
  generated product, demo, task, customer, folder slug, stack, workflow run, or
  UI label. Treat those as task data, selected run state, fixtures, manifests,
  or project-local config, not as the runtime identity.
- Application architecture and code-quality rules: follow OOP, SOLID, DRY,
  clean-code, maintainability, extensibility, and established architecture
  patterns such as clean architecture, microservices, DDD, and equivalent
  stack-appropriate patterns where they fit the stack; keep domain/product
  logic, orchestration, UI, persistence, filesystem, external services, and
  configuration in separate layers with explicit contracts. Reduce duplicated
  knowledge and behavior, but avoid premature abstractions before the shared
  meaning is clear.
- Technology stack inventory: keep
  `tools/project-memory/specs/technology-stack.md` current for GI-enabled
  projects, with verified runtimes, frameworks, package managers, build/test
  tools, storage, services, commands, evidence, and gaps. Follow
  `patterns/TECHNOLOGY_STACK_INVENTORY.md`.
- Feature workflow contracts: when a feature has an agreed runtime workflow,
  loading order, branching state flow, background work, or user-visible
  guarantee, record it in project-local docs and require agents to read it
  before changing that feature. For non-trivial features, keep the feature
  idea, functional description, workflow contract, implementation plan, sprint
  breakdown, task breakdown, definitions of done, and verification linked
  together.
- Encoding safety rules: preserve existing file encodings; avoid rewriting
  source files through PowerShell `Get-Content ... | Set-Content ...` pipelines
  unless both encodings are explicit and correct; prefer patch tools or
  language APIs that read and write UTF-8 explicitly.

For other tools, add tiny redirect files when useful:

- `.github/copilot-instructions.md`
- `CLAUDE.md`
- `GEMINI.md`
- root `README.md` section: `For AI agents: read AGENTS.md first.`

Do not duplicate the whole instruction set everywhere. Keep `AGENTS.md` the source of truth.

## 2. Define Durable Memory

Create a local memory folder, for example:

```text
tools/project-memory/
```

Minimum contents:

- `README.md`: what memory exists and how to use it.
- `STUDY_PLAN.md`: roadmap for understanding the project.
- `instruction-kit.json`: copied instruction-kit provenance and local update
  check configuration, including applied migrations, when the project uses a
  shared instruction library.
- `git-preferences.json`: project-local commit message language preferences.
- Local agent memory database or index, ignored by git when large/generated.
- A command to rebuild the index from source files.
- A command to save durable investigation notes.

Rule: important findings must be written locally, not only said in chat.

When a project reveals a reusable improvement to agent instructions, workflows,
templates, or checklists, write a dated recommendation to the shared instruction
library's `updates/` folder if that library exists. Treat those files as intake
recommendations, not automatically accepted rules.

Use projects as experience sources for `gi`: collect reusable workflows,
failure patterns, token-saving tactics, startup retrieval improvements, and
agent-instruction improvements. Include the observed problem, recommended shared
rule or artifact, evidence paths or commands, expected benefit, risks, and
privacy review.

If no shared instruction library is available, create a local project intake
folder such as:

```text
tools/instruction-updates/
```

or, when the project already has agent memory:

```text
tools/project-memory/instruction-updates/
```

Use this filename pattern:

```text
YYYY-MM-DD_HH-mm-ss_AGENT_RECOMMENDED_GENERAL_INSTRUCTIONS_UPDATES.md
```

Keep project-specific details out of reusable instruction recommendations unless
they are clearly marked as examples. Do not add the shared instruction library
as a dependency, package, submodule, symlink, or runtime reference unless the
user explicitly asks for that.

Recommended pattern: use `tools/project-memory/project_memory.sqlite` as a local
SQLite memory/index for the agent, not as the product database and not as part
of the application runtime. Commit only reviewable docs, schema/scripts, and
Markdown exports when useful. Keep the SQLite file ignored when it is large or
rebuildable.

SQLite agent memory should support targeted queries, for example search by
symbol, path, topic, error, or feature name. Do not dump the database or load it
whole into context. Use small SQL queries with `LIMIT`, and keep durable notes
exportable to Markdown such as `tools/project-memory/NOTES.md`.

Use two project-memory layers:

- Markdown is the human-reviewable layer for concise handoff summaries,
  decisions, architecture notes, and curated exports.
- SQLite is the searchable agent-memory layer for detailed findings,
  file/symbol indexes, references, commands, failures, and evidence-backed notes.

Keep a third distinction inside Markdown memory: handoff summaries are short
session state, while project-memory specifications are durable product truth.
For non-trivial features, business workflows, data models, integrations, and
architecture decisions, write platform-neutral specifications that explain the
behavior, algorithms, business rules, states, failures, and verification without
depending on the current implementation language or framework. Include a current
implementation map as evidence, but do not make code structure the only source
of behavioral truth. Use `patterns/PROJECT_MEMORY_SPECIFICATIONS.md`.

Split project-memory specifications by meaning. Prefer focused files such as
`tools/project-memory/specs/features/<feature>.md`,
`tools/project-memory/specs/business-rules/<domain>.md`,
`tools/project-memory/specs/data-model/<entity>.md`, and
`tools/project-memory/specs/integration-contracts/<boundary>.md` over a single
large document. Keep major architecture rewrites and platform migrations in
`tools/project-memory/architecture-migrations.md`.

Do not use `tools/project-memory/` as a dumping ground for raw work results,
generated product outputs, screenshots, photos, crawled/downloaded files, large
logs, model outputs, build artifacts, export bundles, or run datasets. Store
those files in a project-local artifact/evidence/output/data/docs-asset location
and keep only compact manifests, summaries, checksums, or links in project
memory when needed for a decision, contract, failure, or verification result.

Do not use `tools/` as the default destination for generated product output,
selected-run artifacts, uploaded site contents, screenshots, raw exports, build
bundles, downloaded datasets, or one-off work results. Keep `tools/` for durable
development and agent tooling such as scripts, adapters, bootstrap commands,
deployment helpers, and redacted examples or manifests. Document the project's
artifact, evidence, output, data, docs-asset, build, or release locations.

Do not classify a file as durable tooling from its executable extension. A
single-task Python/PowerShell/shell research probe, exploratory scraper, data
inspection script, or throwaway diagnostic must not go under `tools/` or a new
`tools/research`, `tools/probes`, or `tools/scratch` subtree. Prefer an inline
command. If a file is required, use a documented ignored scratch/temp location
outside `tools/`, remove it after use, and store only necessary results in the
documented evidence or artifact location. Put a script in `tools/` only when it
has a stable reusable contract and an expected future caller.

For projects that depend on, research, vendor, or regularly interact with other
repositories, cloned examples, services, libraries, docs sites, or upstream
tools, keep `tools/project-memory/specs/integration-contracts/connected-projects.md`
as the register of connected projects. Record each project's purpose, business
or architectural role, local folder when applicable, canonical Git or docs URLs,
service IDs or runtime endpoints, owner/source of truth, data/API contract,
setup/update commands, privacy and access boundaries, status, caveats, and why
the current project needs it. Agents should read this register before touching
integrations or external project folders and update it when a connected project
is added, removed, replaced, moved, or given a new role.

Do not blindly migrate all Markdown into SQLite. When Markdown memory becomes
too large to read cheaply, introduce or rebuild the SQLite memory/index and keep
Markdown as the concise reviewable export.

When a project needs retrieval that can later grow into semantic RAG, add a
project-local `tools/project-memory/rag-system.json` from
`templates/rag-system.template.json` and follow
`patterns/RAG_SYSTEM_STRUCTURE.md`. Keep Chroma, Qdrant, pgvector, and similar
stores behind a retrieval adapter so `gi` startup, memory writeback, and prompt
assembly do not depend on one vector database.

Before enabling vector retrieval, prepare semantic-ready chunks and embedding
metadata. Use `patterns/SEMANTIC_RAG_RETRIEVAL.md`, keep the generated
`semantic-corpus.jsonl` ignored, and add a small eval set from
`templates/semantic-retrieval-evals.template.md`.

For analysis, refactoring, migration, or multi-step implementation tasks, create
or update a concise checklist in the project's durable planning location before
editing code. For project-wide or ongoing work, use a shared task file such as
`tools/project-memory/pending-tasks.md`. For a large focused task, create a
dedicated Markdown plan in `tools/project-memory/` with a clear task name.

Task plans should include the goal, planned changes, execution order, risks or
dependencies, and verification steps. Track progress while working and keep the
file concise; do not store full diffs, large logs, generated outputs, secrets,
credentials, or private production data.

After meaningful work on a feature, workflow, business rule, data model,
integration, or architecture, update the relevant project-memory specification
in the same scoped change. Update the handoff summary separately only when the
recent chat state needs to be handed to a future session.

For complex product behavior, create feature workflow contracts in a local docs
or memory area such as `docs/features/` or `tools/project-memory/`. Use
`patterns/FEATURE_WORKFLOW_CONTRACTS.md` and
`templates/FEATURE_WORKFLOW_CONTRACT.template.md` to capture the agreed
workflow, branches, background work, loading/error states, and verification
signals. Before changing a feature with a recorded contract, read it and
preserve its user-visible guarantees unless the user explicitly changes the
agreement. Use one sprint for small features and several sprints for larger
features; break each sprint into concrete tasks that trace back to the feature
workflow or implementation plan. Do not let task lists replace the feature
contract.

Use these default activation limits for generated retrieval stores unless a
project-local `rag-system.json` defines stricter values:

- Add or rebuild SQLite/FTS when tracked text sources exceed 50 files,
  project-memory Markdown/JSON exceeds 25 files or about 200 KB, feature specs
  exceed 10 files, exact retrieval repeatedly misses, or startup restore needs
  too many focused reads.
- Add vector retrieval only after curated specs or notes exist and keyword
  retrieval is insufficient. Consider it when semantic-ready chunks exceed 300,
  curated project-memory specs exceed about 500 KB, feature specs exceed 25
  files, conceptual retrieval misses relevant memory at least three times, or
  several agents need conceptual lookup over the same memory.
- Move to service-grade PostgreSQL, pgvector, Qdrant, or a similar managed
  retrieval service only for measured needs such as concurrent agents, shared
  remote access, permission filtering, backups/snapshots, or corpora above
  roughly 10,000 chunks.

Treat `gi sql` and `gi vector` as diagnostic commands. They should read
`tools/project-memory/rag-system.json`, run local stats/status helpers when
available, compare current counts with activation limits, and report whether
SQL/FTS or vector retrieval is absent, current, stale, or recommended. They do
not create external services or install heavy dependencies by default.

## 3. Add A Startup Script

Create one command that restores project context.

Example:

```powershell
.\tools\agent-start.ps1
```

It should print:

- `AGENTS.md`
- working agreements
- git commit language preferences
- instruction-kit update notices
- latest summary
- `git status --short`
- useful `git diff --stat` information
- next recommended commands

The goal is that a new chat can become useful in minutes.

Startup scripts must stay compact. Do not dump large files, full runbooks, full
logs, full SQLite contents, generated files, or full diffs. Use line guards and
targeted queries, such as `Get-Content -TotalCount`, `Get-Content -Tail`,
`Select-String`, and `git diff --stat` on PowerShell.

If the project has `tools/project-memory/instruction-kit.json`, the startup
script may compare its installed version with a configured local shared
instruction library's `VERSION.md` and print a compact update notice. It should
point to accepted release artifacts such as `CHANGELOG.md`, not to `updates/`.

For applying updates, use `patterns/INSTRUCTION_KIT_MIGRATIONS.md` and a
project-local command copied from
`templates/check-instruction-kit-updates.template.ps1`.

On startup or after context loss, the agent should continue from recorded state,
not from memory alone. It should read the latest summary, inspect relevant diffs,
and only then edit files.

Use `patterns/RAG_STARTUP_FLOW.md` for token-conscious context restoration and
`patterns/FIRST_MESSAGE_HANDLING.md` for first-message title or bootstrap
behavior.

## 4. Define Optional Skills

Use `patterns/SKILL_MODULES.md` to decide whether a reusable capability should
be a rule, pattern, template, or skill.

Create a skill only when the capability has a clear trigger and is too large or
too situational for always-loaded project instructions. A typical project-local
skill lives under:

```text
skills/TODO-skill-name/SKILL.md
```

Use `templates/SKILL.template.md` as a starter. Keep skills self-contained,
small, and free of secrets or project-specific data unless the project owns that
skill locally.

## 5. Write Working Agreements

Create:

```text
tools/AGENT_WORKING_AGREEMENTS.md
```

Include:

- Do not revert user changes unless explicitly requested.
- Treat dirty worktrees as normal.
- Whether the agent may commit or only edit. Default safe rule: the agent edits
  and verifies; the user reviews and commits, unless the project says otherwise.
- Preferred edit method. For manual edits, prefer patch-style edits that keep
  changes scoped and reviewable.
- Prefer small scoped changes.
- Main project folders.
- Where logs and generated files live.
- When to ask before expanding scope.
- If a change needs files outside the agreed working area, say so before
  expanding scope.

## 6. Write A Runbook

Create:

```text
tools/AGENT_RUNBOOK.md
```

It should answer:

- How to install dependencies.
- How to run the app.
- How to run tests.
- How to build.
- How to smoke-check the most important workflow.
- How to inspect logs.
- Known environmental caveats.

Every command should be copy-pasteable.

## 7. Keep Handoff Summaries

Create:

```text
tools/summary/
```

After meaningful work, write a concise summary named:

```text
YYYY-MM-DD_HH-mm-ss_AGENT_WORK_SUMMARY.md
```

Include:

- Current state.
- Thread essence: user intent, important decisions, and the problem being solved.
- What changed in code, architecture, product behavior, or business logic.
- Verification evidence and meaningful check results.
- Known failures or caveats.
- Next best steps.
- Repository state only when it affects the next handoff, such as uncommitted
  work, unresolved conflicts, failed pushes, or a required follow-up.

Do not fill handoff summaries with routine command bookkeeping such as
successful `gi push`, `gi commit`, staging counts, git directives, branch names,
push targets, or commit hashes when those facts are recoverable from git logs or
command history. If a step-by-step protocol is useful, write it as a separate
`Thread Timeline` section or file only when the user asks or the timeline
materially helps the handoff. Summaries are for handoff. Durable knowledge
belongs in project memory notes.

When resuming from a handoff or answering where a thread stopped, reconcile the
summary with the latest visible thread conclusion, user screenshots, or direct
quotes. Prefer the last explicit architectural/product decision, open question,
or agreed next direction over incidental caveats. Do not turn an unverified
caveat, environment variable, skipped check, or old next-step bullet into the
active task unless the user selects it or it blocks the stated goal.

## 8. Map The Architecture Early

Before large changes, build a first map:

- Entry points.
- Modules/packages/assemblies.
- Dependency graph.
- Data flow.
- Runtime lifecycle.
- Config/secrets boundaries.
- Storage/database/API boundaries.
- Assets/templates/UI/routes as applicable.
- Tests and automation.

Do not try to understand everything in one pass. Build a searchable index and record small verified findings.

Use `patterns/CONFIGURATION_BOUNDARIES.md` when adding or refactoring runtime
settings. Treat accepted instruction-kit updates that introduce the
configuration-boundary rule as a prompt to audit existing code for hard-coded
deployment, user, environment, host, service, credential, path, feature-flag,
and operational values, then refactor scoped findings into config as part of the
migration when it is safe.

Use `patterns/DEVELOPMENT_TOOL_PRODUCT_BOUNDARIES.md` when building or changing
orchestrators, task managers, agent harnesses, generators, scaffolding tools, or
workflow UIs. Verify that no sample product, demo domain, customer name, folder
slug, stack, or test task is treated as a built-in runtime concept. Detailed
workflow logs should describe only the selected or active run; completed runs
should collapse by default or render as compact final status unless the user is
debugging them.

Before meaningful implementation, choose an architecture shape that fits the
stack and keep it visible in code: ports/adapters, layered architecture, clean
architecture, MVC/MVVM, feature modules, service contracts, or another
established pattern. Apply SOLID where OOP exists, DRY where duplicated
knowledge or behavior has a clear shared meaning, and equivalent module and
contract boundaries in functional or scripting stacks. Do not mix orchestration,
domain logic, UI rendering, persistence, external service calls, and config
loading in one unstructured layer.

## 9. Establish Quality Gates

Every project should define minimum checks:

- After changing any artifact, verify it once: reread the edited code, JSON,
  config, docs, generated metadata, or command output instead of assuming the
  edit landed correctly.
- Fast syntax/type check.
- Unit tests.
- Integration or smoke test for the main workflow.
- Build/package command.
- Lint/format command when available.
- Log inspection command for runtime systems.
- If debugging or a check requires closing the project, editor, app, or other
  user-visible process, ask first and offer a choice: allow the close once, or
  allow the same close action for the rest of the current chat.
- Launch applications, editors, browsers, and GUI tools quietly in the
  background whenever possible. Do not steal keyboard focus, move the cursor, or
  bring the launched app to the foreground, because the user may be typing in
  another project.

If a check cannot run locally, document why.

## 10. Decide Git Rules

Write the policy clearly:

- Who commits.
- Branch naming.
- Whether generated files are committed.
- What must never be committed.
- How to handle unrelated dirty files.
- Default diff review command, such as `git diff --stat`.
- Whether full diffs are allowed in chat. Default: avoid full diff dumps unless
  the user explicitly asks.
- Commit message language preferences. Default: English primary, with optional
  additional languages stored in `tools/project-memory/git-preferences.json`.

Default safe rule: the agent edits and verifies; the user reviews and commits.
The agent commits only when the user explicitly asks. Use
`patterns/GIT_WORKFLOW.md` for the reusable policy and
`templates/select-git-commit-languages.template.ps1` to configure project-local
commit-message languages. The startup script may also expose the same selector
through `tools/agent-start.ps1 -ConfigureGitCommitLanguages`.

## 11. Protect Secrets And Generated Noise

Before real work starts:

- Review `.gitignore`.
- Ignore local databases, logs, cache folders, build outputs, temp folders.
- During repository cleanup or GitHub preparation, do not remove `AGENTS.md`,
  `tools/`, `tools/project-memory/`, `skills/`, bootstrap/update/deploy scripts,
  or agent-facing instruction/config files just because they look internal.
  Inspect them first and preserve them when they provide RAG startup, durable
  project memory, update flow, deployment, or agent workflow support.
- Classify SQLite/database files before deleting or committing them. Generated
  agent-memory indexes such as `tools/project-memory/project_memory.sqlite`
  should usually stay ignored and rebuildable, while README files, Markdown/JSON
  exports, schemas, and indexing scripts should be committed when useful.
- Never store credentials in summaries or notes.
- Document where secret/config examples live.
- Keep deploy/user/environment/system-dependent values out of source code and
  shared instructions. Use redacted config examples, environment variable names,
  or service identifiers instead of real hostnames, ports, credentials, private
  folders, machine-specific absolute paths, or user-specific options.

## 12. Make The First Useful Vertical Slice

For a new product, avoid spending the first phase only on structure.

Build one thin but real workflow:

- UI/API entry.
- Domain action.
- Persistence or external integration if needed.
- Test or smoke check.
- Logging/observability.

Then expand around a working spine.

## 13. End Every Session Cleanly

Before stopping:

- Run the relevant checks.
- Record failures honestly.
- Update summary.
- Save durable findings as notes.
- Leave `git status --short` understandable.

The next chat should never have to reconstruct the previous session from vibes.

## Minimal New Project Checklist

- [ ] Root `AGENTS.md`
- [ ] Root `README.md` with human setup and AI redirect
- [ ] `.gitignore`
- [ ] `tools/AGENT_WORKING_AGREEMENTS.md`
- [ ] `tools/AGENT_RUNBOOK.md`
- [ ] `tools/summary/`
- [ ] `tools/project-memory/README.md`
- [ ] `tools/project-memory/STUDY_PLAN.md`
- [ ] `tools/project-memory/instruction-kit.json`
- [ ] `tools/project-memory/git-preferences.json`
- [ ] `tools/select-git-commit-languages.ps1`
- [ ] `tools/check-instruction-kit-updates.ps1`
- [ ] Optional project-local skills under `skills/`
- [ ] Optional local agent memory SQLite/index script
- [ ] Optional Markdown export for durable agent notes
- [ ] Two-layer memory policy: concise Markdown for review, SQLite for
  searchable detailed agent memory when Markdown becomes too large
- [ ] Startup script
- [ ] Test/build/run commands
- [ ] Secret/config policy
- [ ] First handoff summary

## Token Budget Rule

The agent must not load the whole repository, full chat history, or all summaries by default.

Startup context should include only:
- AGENTS.md
- latest handoff summary
- relevant memory notes found by search
- current git status
- `git diff --stat`, not full `git diff`
- exact files needed for the task

Prefer retrieval over dumping context.
Prefer short summaries over raw logs.
Prefer file excerpts over full files.
Prefer targeted searches over full diff dumps.
Avoid broad artifacts, full check matrices, large logs, and whole-file reads
unless the user asks for that scope or targeted investigation cannot isolate the
failure.

## Instruction Update Intake

The `general-instructions` repository may receive dated recommendation files
from different projects under:

```text
updates/
```

Treat those files as an intake queue for maintaining `general-instructions`, not
as automatically accepted rules.

External projects:

- May write dated recommendations to `updates/` when the shared library is
  available.
- Must not read `updates/` during startup or bootstrap.
- Must not add the shared library as a dependency, package, submodule, symlink,
  or runtime reference unless the user explicitly asks.

When maintaining this library:

- Review update files by date, newest first.
- Read only the specific update being evaluated, not the whole folder by
  default.
- Extract reusable rules, patterns, templates, or checklist items into the main
  library.
- Keep project-specific details out of shared instructions.
- Treat source project names, evidence paths, task-manager notes, and owner
  labels in recommendations as provenance only. They are not permission to read,
  search, edit, or inspect the source project. Ask the user or that project's
  owner for an explicit concrete path and action before crossing the current
  repository boundary.
- Preserve token economy: avoid recommendations that encourage dumping large
  files, full diffs, logs, SQLite contents, generated outputs, or all memory.
- Remember accepted updates by committing the resulting instruction changes.

## Usage Awareness

Prefer retrieval, concise summaries, targeted checks, and scoped edits
throughout the session. Do not wait until usage is nearly exhausted to become
token-conscious.

Before expensive operations such as full repository scans, repeated retries,
large multi-file edits, or huge context restores, confirm that the scope is
needed for the user's goal.
