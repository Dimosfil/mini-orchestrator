# Agent Instructions

## Project

This repository is the starting workspace for a mini orchestrator for AI-agent
workflows. The current durable product context is
`mini-orchestrator-plan.md`: a plan for a minimal plan -> execute -> validate
cycle where a coordinator model plans and validates work, and an executor model
performs bounded technical steps.

The runtime, package layout, install command, test command, and build command
are not defined yet. Before implementation, derive them from the plan or an
explicit user decision and record the chosen contract in local project docs.

## Restore Context

If the user only sends a short greeting, thanks, acknowledgement, or
status-neutral message, do not run startup restore or read project files. Reply
briefly and ask what they want to do next.

Start here:

```powershell
.\tools\agent-start.ps1
```

If the startup script is unavailable, read only the smallest useful slices of:

- `AGENTS.md`
- latest file in `tools/summary/`
- `tools/AGENT_WORKING_AGREEMENTS.md`
- `tools/AGENT_RUNBOOK.md`
- relevant notes in `tools/project-memory/`

Use the RAG startup flow: retrieve only task-relevant context, search memory by
specific terms, and query SQLite memory only with small `LIMIT`s. For `gi start`,
`gi restore`, or title-only first messages, restore only enough orientation for
the next turn; do not read full summaries, runbooks, memory notes, logs, or diffs
unless a concrete task needs them.

During `gi start` or `gi restore`, do not treat remembered plans, stale task
notes, old refactoring phases, or local commits ahead of a remote as the next
action. Mention them only as compact context when relevant, then ask for the
user's current task instead of offering to continue, run, push, or finish them.

Treat `init <source>`, `инит <source>`, `инициализируй <source>`, and
`инит правила <source>` as shared-instruction bootstrap/startup requests when
`<source>` points to `https://github.com/Dimosfil/general-instructions.git`, the
current shared-instruction checkout/cache, `GENERAL_INSTRUCTIONS_HOME`, or
another known `general-instructions` source. Read existing instruction files and
follow GI bootstrap rules; never reinterpret these forms as `git init`, folder
creation, OpenCode setup, project creation, `npm init`, or `python -m venv`
unless the user explicitly names that action.

Treat `gi help`, `gi хелп`, `ги help`, `ги хелп`, `gi commands`,
`gi команды`, and `ги команды` as requests to show a compact list of available
GI chat commands with short descriptions. Read the local command index such as
`COMMANDS.md` when present, prefer project-local command additions over the
shared baseline, and keep the answer informational: do not run startup restore,
resume old work, call task managers, mutate files, or execute the listed
commands unless the user asks for a specific command next.

The copied instruction kit is a token-economy and RAG-startup layer for this
project. Use it to restore only the needed context from local instructions,
handoff summaries, targeted searches, and project memory instead of reading the
whole repository or printing broad outputs.

When this project needs retrieval that can grow beyond Markdown and SQLite FTS,
use `patterns/RAG_SYSTEM_STRUCTURE.md` and a project-local
`tools/project-memory/rag-system.json`. Keep Chroma, Qdrant, pgvector, and
similar stores behind retrieval adapters so startup, prompt assembly, and memory
writeback do not depend on one vector database.

Before enabling vector retrieval, prepare semantic-ready chunks, embedding
metadata, and a small eval set. Use `patterns/SEMANTIC_RAG_RETRIEVAL.md`, keep
generated embedding corpora and vector indexes ignored when rebuildable, and do
not mix embeddings from different models in one collection version.

Use structured memory such as SQLite for deterministic project facts and graphs:
file paths, symbols, exact references, GUIDs, generated identifiers, asset links,
reverse dependencies, commands, failures, and evidence-backed notes. Use vector
retrieval only as a second semantic layer for conceptual questions over curated
notes, summaries, architecture docs, and selected chunks. Do not replace exact
graph queries with embeddings, and verify current source files before editing
because memory indexes can be stale.

Treat `tools/summary/` as compact handoff state for the current or recent chat.
Treat `tools/project-memory/` as durable product and project knowledge. For every
non-trivial feature, business workflow, or architecture decision, keep
platform-neutral project-memory specifications that describe the behavior,
business rules, algorithms, state transitions, failure handling, verification,
and current implementation map. Write them so another agent could rebuild the
project on a different language, platform, or framework and preserve the same
behavior. Split specifications by meaning instead of one giant file. Keep major
rewrites in `tools/project-memory/architecture-migrations.md`.

Keep GI agent-runtime neutral. These instructions are for any compatible AI
agent or assistant, not only Codex. Mention Codex only when a rule is about a
Codex-specific tool, folder, permission model, app surface, or workflow.

Treat `cached input` as a symptom, not the main optimization target. Keep total
live context small by starting new sessions for unrelated tasks, using compact
handoff summaries instead of long investigation history, and splitting multi-step
R&D when later steps do not need the full previous reasoning trace.

## Durable Memory

Durable project knowledge lives in:

```text
tools/project-memory/
```

Important findings should be written there or in a handoff summary, not only
left in chat.

For analysis, refactoring, migration, or multi-step implementation tasks, create
or update a concise checklist in `tools/project-memory/pending-tasks.md` or a
dedicated task plan in `tools/project-memory/` before editing code. Keep plans
task-relevant and update progress as meaningful steps complete.

When this project reveals a reusable improvement to agent instructions,
workflows, templates, or checklists, write a dated recommendation to the shared
instruction library's `updates/` folder if it is available. If it is not
available, use a local intake folder such as `tools/instruction-updates/` or
`tools/project-memory/instruction-updates/`. Treat recommendations as intake,
not accepted rules.

Use this project as an experience source for `gi`: capture reusable workflows,
failure patterns, token-saving tactics, and agent-instruction improvements that
could help other projects. Keep recommendations concise, evidence-backed, and
free of secrets, private user data, production data, and unnecessary
project-specific details.

When maintaining a shared instruction-library project, a user request to add or
accept a reusable rule may also be treated as approval to finish that accepted
instruction change end to end: update the relevant files, verify them, commit
and push only the scoped rule changes, then run the `gi обновить` update flow
when accepted instruction-kit propagation applies. Do not include unrelated
dirty worktree changes, secrets, private data, or generated noise; do not
recurse into another commit/push merely because this finish rule itself was
added or run.

Accepted RAG, startup, command, workflow, and agent-safety rules must apply to
both the shared instruction source repository and every consuming project. When
changing an accepted reusable rule, update the source repository's live files,
the copied-project templates, accepted migrations, version/changelog, and local
instruction-kit metadata so future `gi обновить` runs can propagate the same
rule.

## Common Commands

Install dependencies:

```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1
python -m pip install -e .
```

Run:

```powershell
python -m mini_orchestrator "прочитай AGENTS.md"
```

Test:

```powershell
# Run a smoke command for the MVP.
python -m mini_orchestrator "search AGENTS"
```

Build:

```powershell
# No build pipeline exists yet.
```

Inspect logs:

```powershell
# No runtime logs exist yet.
```

## Windows Command Policy

- Prefer PowerShell-native networking commands such as `Invoke-RestMethod` and
  `Invoke-WebRequest` instead of `curl.exe`.
- Do not probe for `curl.exe` with `where.exe curl` or `Get-Command curl` unless
  the user explicitly asks for curl diagnostics.
- Prefer trusted helper binaries from `%USERPROFILE%\.codex\bin` before
  WindowsApps or System32 shims.
- If Windows or antivirus tools block agent commands with `Access denied`,
  trust narrow agent-owned tool folders such as `.codex\.sandbox-bin\` and
  `.codex\bin\`; do not add broad exclusions for System32 or PowerShell itself.

## Working Areas

- Source: repository root until a `src/` layout is chosen.
- Tests: not created yet; use `tests/` unless the selected stack implies
  another standard layout.
- Tools: `tools/`
- Summaries: `tools/summary/`
- Project memory: `tools/project-memory/`

## Rules

- Do not revert user changes unless explicitly requested.
- Treat dirty worktrees as normal.
- Keep changes scoped to the current task.
- When a feature has an agreed runtime workflow, loading order, branching state
  flow, background work, or user-visible guarantee, record it in project-local
  docs or project memory. Before changing that feature, read the relevant
  feature workflow contract and preserve its guarantees unless the user
  explicitly changes the agreement.
- For non-trivial feature work, keep the feature idea, functional description,
  workflow contract, implementation plan, sprint breakdown, task breakdown,
  definitions of done, and verification linked together. Tasks do not replace
  the feature contract: tasks say what to change, while the contract says what
  behavior must remain true.
- For non-trivial business rules, data models, integrations, algorithms, or
  architecture, update the relevant project-memory specification in the same
  scoped change. A handoff summary does not replace durable project memory.
- When preparing this project for a repository, publishing to GitHub, or
  removing "unneeded" files, do not classify `AGENTS.md`, `tools/`,
  `tools/project-memory/`, `skills/`, bootstrap scripts, update scripts, deploy
  scripts, or agent-facing instruction/config files as removable only because
  they look internal or tool-related. Inspect their purpose first and treat them
  as possible RAG/startup infrastructure. Delete them only when the user
  explicitly confirms they are temporary or unrelated to the project.
- During repository cleanup, classify SQLite and database files before acting.
  Do not delete or commit `*.sqlite`, `*.sqlite3`, or `*.db` files solely
  because they are binary or local-looking. Keep generated agent-memory indexes
  such as `tools/project-memory/project_memory.sqlite` ignored when they are
  rebuildable, and commit the reviewable README, Markdown/JSON memory exports,
  schema, and indexing scripts instead. Do not commit databases containing
  secrets, private data, telemetry, task-manager state, absolute local paths, or
  agent conversation history.
- Do not hard-code values that can change by deployment, user choice, runtime
  environment, host machine, service discovery, credentials, filesystem layout,
  feature flags, or operational policy. Keep application code focused on logic,
  constants, and internal defaults; move deploy/user/environment/system values
  into documented project-local configuration, environment variables, or
  service discovery records. Avoid embedding machine-specific absolute paths in
  source or shared instructions; when paths are accepted from config, resolve
  and validate them as absolute paths at startup or I/O boundaries. When
  applying this rule to existing projects, audit and refactor relevant
  hard-coded values instead of only adding the rule text.
- Preserve text encodings when editing files. On Windows, do not rewrite source
  files with PowerShell pipelines such as `Get-Content ... | Set-Content ...`
  unless both read and write encodings are explicit and known correct. Prefer
  `apply_patch`, editor-native saves, or language APIs that read and write the
  file with an explicit encoding such as UTF-8. If non-ASCII text appears as
  mojibake after a command, stop, restore the last clean file version, and
  reapply only the intended small patch.
- Ask before destructive operations, broad refactors, or unrelated scope
  expansion.
- Treat this project root as the filesystem boundary for normal work. Do not
  read, search, edit, create, delete, move, or inspect files in another project
  or arbitrary external folder unless the user gives an explicit concrete path
  and action. Use APIs, connectors, or task-manager endpoints for cross-project
  communication.
- Treat `.\others\` under the current workspace parent, or another
  project-local relative path named by local instructions, as the standard local
  parent folder for third-party projects, cloned external repositories, and
  vendor experiments when no more specific destination is provided. This default
  folder is configurable: if the user gives another path or project-local
  instructions define another third-party workspace parent, use that instead. Do
  not mix third-party projects into the current project workspace.
- Treat `gi config`, `gi конфиг`, `ги конфиг`, `gi config service`,
  `ги конфиг сервис`, `ги конфиг сервис url=<url>`, and
  `ги конфиг сервис урл=<url>` as requests to get or set the bootstrap config
  for the config/discovery service. Read a
  project-local override only if local instructions define one, then read GI
  main config from the configured shared-instruction source repo checkout/cache,
  the current shared-instruction checkout, or `GENERAL_INSTRUCTIONS_HOME`. Use
  its `config/gi-main.json` `configServiceUrl` to query the config service.
  Resolve local app and task-manager runtime URLs by service id through
  config-service; project task-manager config should keep only the selected
  manager name/id and non-secret project preferences. For the `url=<url>` form,
  validate a full `http://` or `https://` URL with no secrets, update the shared
  `configServiceUrl` or the explicit project-local override, and tell services
  to use that URL for registration and discovery. Do not scan sibling project
  folders, guess ports, copy URLs from old task-manager memory, or use stale
  task-manager records as a runtime fallback.
- Treat task-manager sync commands as routine execution steps, similar in
  certainty to `gi commit`, `gi push`, or FTP deploy commands after the user has
  supplied the content or selected workflow. A fast or weaker model may execute
  these commands, but it must still follow the manager contract exactly: do not
  replace manager API work with `project-memory`, pending-task notes, guessed
  commands, raw intake receipts, local checklists, or "tell me the exact
  command" fallback. If discovery, auth, contract, capability, payload shape, or
  readback is missing, stop with the exact blocker.
- For agent-facing HTTP services, prefer a service-owned guide endpoint plus a
  strict contract endpoint. Resolve runtime URLs through config-service. Read
  `endpoints.guide` first when present, then `endpoints.contract` before
  sending state-changing requests. Treat the guide as onboarding and the
  contract as workflow validation. If they disagree, stop and report the
  mismatch. Do not infer permissions from filesystem paths, stale memory, old
  dashboard URLs, or raw task receipts.
- Treat `gi manager`, `gi tm`, `gi manager test`, `ги менеджер`,
  `ги манагер`, and equivalent task-manager status or test wording as requests
  to inspect the configured task manager through config-service. Read the
  enabled manager id or `service_id` from project-local task-manager config,
  resolve it through `GET /services/{serviceId}`, read `endpoints.guide` when
  present, read `endpoints.contract`, then use `endpoints.api` for documented
  manager operations. Stop with the exact blocker if the manager id is missing,
  config-service is unavailable, no matching service record exists, or the
  guide/contract lacks the requested capability. Do not fall back to `base_url`,
  stale task-manager memory, port scans, sibling projects, or guessed endpoints.
- Treat `gi config service on`, `gi config service off`, `ги конфиг сервис on`,
  and `ги конфиг сервис off` as requests to set the current application's
  project-local config-service self-registration flag. `on` means the app
  should publish or refresh its own service record during startup; `off` means
  it must not. Do not reinterpret this as starting or stopping config-service
  itself. When setting `on`, first confirm a config-service URL is already
  configured in the same local config area or documented GI bootstrap config; if
  no URL is configured, tell the user to set `gi config service url=<url>`
  before enabling self-registration. Ask one short question if no local config
  location is documented.
- For web-facing applications that expose a port, HTTP API, web UI, task-manager
  service, or local daemon endpoint, require a live config-service config check
  on every process startup before publishing or refreshing the app's own service
  record. On startup, query the app's own `service_id`; if no record exists,
  create one with the current port and documented endpoints, and if the record
  exists but the port or endpoints changed, refresh it. Desktop apps, CLI tools,
  libraries, scripts, and other non-web applications must not query or publish
  to config-service during normal startup unless local instructions explicitly
  define a discoverable web/API runtime. Use cached config only as an explicit
  degraded-startup fallback documented by local run instructions.
- Treat `gi ftp`, `ги фтп`, `gi ftp push`, `ги фтп пуш`, `gi upload ftp`,
  `gi deploy ftp`, and `gi залей на фтп` as requests to upload this project's
  configured build output to FTP, FTPS, or SFTP. Treat `gi ftp config`,
  `gi ftp конфиг`, and `ги фтп конфиг` as requests to create, inspect, or update
  the project-local FTP/SFTP config without uploading. Treat `gi ftp folder`,
  `gi ftp папка`, and `ги фтп папка` as requests to inspect, choose, or update
  the remote upload folder (`remotePath`) without uploading. Treat
  `gi ftp service`, `gi ftp сервис`, and `ги фтп сервис` as requests to
  manually register, inspect, or select an FTP/FTPS/SFTP service record in
  config-service without uploading. Read project-local deploy instructions and
  `tools/deploy/ftp.local.json` first;
  when this project needs FTP and local config does not name a target service,
  query config-service for FTP-capable services. If exactly one matching service
  exists, use it after verifying its contract; if several exist, ask the user to
  choose with the same numbered Markdown checkbox style used by language
  selection. Keep secrets out of config-service: store only discovery metadata
  and secret references such as environment variable names. Keep project-specific
  deploy settings in the separate project-local config file rather than shared
  instructions or chat history. Prefer `tools/deploy/ftp.local.example.json`
  only as a redacted shape. Do not commit hostnames, usernames, passwords,
  tokens, private keys, or private remote paths unless project policy explicitly
  marks them non-secret.
- Treat `gi reboot`, `ги ребут`, `gi restart`, and `ги рестарт` as requests to
  start or restart the current application using project-local run instructions.
  If the app is running, restart it; if it is not running, start it. Launch in
  the background so focus does not jump away from the user's current window.
- Treat `gi first test`, `gi первый тест`, and `ги первый тест` as requests to
  verify the current application's first-launch experience by resetting only
  documented project-owned app cache, generated state, temporary first-run
  profiles, and rebuildable local app settings. Read project-local run, cleanup,
  cache reset, and test instructions first. Do not delete user documents,
  production data, secrets, credentials, external service data, shared system
  caches, sibling projects, or arbitrary user-home folders. If exact reset
  paths, keys, scripts, or commands are missing, ask one short clarification
  question instead of guessing. After reset, start the app, run the documented
  first-launch smoke/onboarding checks, and report what was cleared, what
  passed, and what was intentionally left untouched.
- Treat `gi install`, `gi инсталл`, `ги инсталл`, and clear typo variants as
  requests to build the current project and produce an installer. Read local
  build/package instructions, resolve the application version from project
  metadata, run the packaging command, and verify the current installer
  artifact. `restore`, dependency install, build, and test checks are
  prerequisites only; do not report `gi install` complete or the project
  installed/restored when only those checks ran.
- Treat `gi sql`, `gi sqlite`, `ги sql`, `ги sqlite`, `gi vector`,
  `gi вектор`, and `ги вектор` as requests to inspect project-memory retrieval
  readiness and current metrics. For SQL, read `tools/project-memory/rag-system.json`
  when present, run the local index stats command when available, count
  reviewable project-memory/spec files, compare the numbers with configured or
  default SQLite activation limits, and report whether SQLite/FTS is absent,
  current, stale, or recommended. For vector, read vector and embedding metadata,
  check semantic corpus size and chunk count, run vector adapter status when
  available, compare the numbers with vector activation limits, and report
  collection, record count, index path, freshness caveats, and readiness. These
  are inspection commands by default; do not create external services, install
  heavy dependencies, upload data, or index private sources unless the user
  explicitly asks and project-local rules allow it.
- Treat `gi root rebuild`, `gi rag rebuild`, `ги рут ребилд`,
  `ги раг ребилд`, and equivalent full-RAG rebuild wording as requests to
  rebuild the current project's entire configured RAG/project-memory retrieval
  system from approved sources. This is a heavy command and requires explicit
  user confirmation immediately before running the full rebuild. Before asking,
  read `tools/project-memory/rag-system.json`, list configured rebuild nodes,
  generated paths that may be replaced, local scripts or adapters, and privacy
  exclusions. After success, run configured stats/status/eval checks, update
  local rebuild state such as `last_full_rebuild_migration` or per-node markers
  when present, and report generated artifacts without committing rebuildable
  indexes.
- Treat `gi root rebuild sql`, `gi rag rebuild sql`, `gi root rebuild vector`,
  `gi rag rebuild vector`, `gi root rebuild chunks`,
  `gi root rebuild manifest`, `gi root rebuild evals`, and Russian equivalents
  such as `ги рут ребилд sql`, `ги рут ребилд вектор`,
  `ги рут ребилд чанки`, `ги рут ребилд манифест`, and
  `ги рут ребилд тесты` as requests to rebuild only the named RAG node. Read
  `rag-system.json`, run only the documented node command or local helper, then
  verify that node's status. Ask one short clarification question if the node is
  not configured.
- During `gi обновить`, inspect each newly applied migration. If a migration
  changes RAG source rules, chunking, embedding metadata, SQLite/vector schemas,
  retrieval adapters, or project-memory index scripts, check `rag-system.json`
  rebuild state. If the project has not rebuilt affected RAG nodes for that
  migration, tell the user which nodes are stale and ask for confirmation before
  running the full `gi root rebuild`; for narrow migrations, run or offer the
  smallest documented node rebuild that satisfies the migration. Do not mark
  RAG rebuild state current until rebuild and status checks succeed.
- Treat nested checkouts, vendored repositories, cloned examples, and
  third-party source trees as separate scope. Do not inspect them as part of the
  main project unless the user explicitly asks, the task is about that nested
  tree, or local instructions identify it as an active workspace component.
- Treat user-home application data and personal telemetry as private external
  sources. Do not read `.codex`, `.cursor`, IDE logs, browser profiles, shell
  history, application SQLite databases, or local app logs outside the project
  root unless the user gives an explicit path and action. For analyzer tasks,
  prefer mock or sample data, or ask for permission to inspect a specific file.
- Treat product plans, `apps.txt`, summaries, and task-manager notes as intent
  signals only. They are not permission to read private local data sources.
- If a required file, skill, config, script, endpoint, task, or other entity is
  missing or not found, first reread the relevant local instructions, runbook,
  project memory, and accepted instruction-kit artifacts for the current scope.
  If the entity is still missing, ask the user a short clarification question.
  Do not use another project folder or the shared instruction library as a
  runtime fallback unless the user explicitly gives that path and action.
- Prefer one language command with three ordered choices when the user wants
  language preferences for project work. Treat `gi language`, `gi язык`, `ги язык`,
  `gi project language`, `gi проект язык`, `ги проект язык`,
  `gi язык проекта`, and `ги язык проекта` as requests to configure, in order:
  project working environment languages, commit-message languages, and task
  languages in
  `tools/project-memory/system-preferences.json` and
  `tools/project-memory/git-preferences.json`.
- Apply the configured project working-environment language order to plans,
  checklists, progress updates,
  final answers, clarifying questions, and user-facing explanations. Do not use
  it to rewrite existing task text, code, commands, logs, quoted text, or a
  response language the user explicitly requested for a specific message.
- Apply the configured task language order to agent-created task titles, task
  descriptions, and task-manager updates.
- For task titles, descriptions, and task-manager updates, treat the first
  configured task language as the main language. If exactly one task language is
  configured, write task text only in that language. If multiple task languages
  are configured, write the main-language text first and then add one clear
  translation per additional language. Do not duplicate the same content twice
  in one language, and do not mix untranslated labels, templates, or Definition
  of Done text from another configured language into the main-language text.
- For each `gi язык` choice, preserve the user's selected order. The first
  selected language in each choice is primary for that surface.
- Do not commit secrets, credentials, local databases, logs, or generated caches.
- Do not print full `git diff` output by default. Prefer `git diff --stat` and
  targeted queries for relevant files or patterns.
- For first-pass project study, read local instructions, README, manifests, and
  config entry points before building a file map. Use recursive scans only after
  a targeted search fails or the task clearly requires repository-wide
  inventory.
- When creating or running a test, smoke-check, or verification plan, verify
  exact commands, CLI flags, ports, routes, health endpoints, request payload
  fields, and environment variables from current project-local instructions,
  runbooks, manifests, config entry points, or source code. Treat handoff
  summaries, task notes, screenshots, and old chat examples as status evidence,
  not as authoritative command contracts; do not reuse stale ports, payloads, or
  flags without checking the current project.
- Do not read large files in full by default, including large `index.html`,
  bundled JS/CSS, logs, lockfiles, generated files, and build artifacts. Prefer
  targeted searches, heads, tails, or small line ranges such as
  `Get-Content -TotalCount`, `Get-Content -Tail`, and `Select-String` on
  PowerShell.
- For verification, count or query HTML elements programmatically instead of
  printing the whole HTML document.
- Do not produce broad artifacts, such as zip archives, or run full check
  matrices unless the user explicitly asks for that scope.
- Final responses should summarize only the changes, checks, and current status;
  do not restate the full investigation context.
- Search for specific symbols, paths, errors, or patterns before doing broad
  repository scans.
- Do not print large logs. Prefer tails and targeted error searches.
- Keep progress updates phase-level, not command-level. Do not narrate after
  every command batch, report counters such as "ran 4 commands", or live-blog
  each intermediate hypothesis. Update when the phase changes, a meaningful
  finding changes the next step, a blocker appears, or work has been quiet long
  enough that the user needs reassurance.
- Do not duplicate tool-run counters that the chat UI may show automatically;
  system UI counters are not agent progress updates.
- Startup restore must be compact; do not dump large files, full runbooks, full
  SQLite contents, full logs, generated outputs, or full diffs.
- `gi start` and `gi restore` must not promote remembered plans, old task notes,
  or local commits ahead of a remote into suggested next actions unless the user
  explicitly asks to continue, run, push, or finish them.
- Treat short greetings, thanks, acknowledgements, and status-neutral messages
  as no-ops unless they include an explicit task, path, command, error, or
  project question. Do not run startup restore for those messages.
- Treat screenshots, logs, pasted errors, or other bug evidence as requests for
  analysis first. Explain the likely issue and ask what action the user wants
  before editing files, unless the user explicitly says to fix it, such as
  `fix`, `почини`, or `gi почини`.
- When the user explicitly says to fix an issue, treat that as approval to take
  required low-risk implementation and verification actions without an extra
  confirmation prompt, including rebuilding, restarting the affected local
  process, or closing a currently running app window that blocks single-instance
  verification. Still ask before destructive actions, possible data loss,
  credential or secret handling, external system changes, or unrelated scope.
- Keep commit-message language preferences separate from the agent's
  user-facing working language unless the user uses the unified project-language
  command.
- If `gi язык` or an equivalent unified project-language command is sent
  without explicit languages, run a three-step chat flow instead of asking for
  one free-form line. At each step, show the same numbered Markdown checklist of
  available languages with the current selection checked, name the current
  surface, and tell the user they may reply with numbers or language names.
  Render each option as a task-list bullet with the number inside the label,
  such as `- [x] 1. English`; do not use ordered-task syntax such as
  `1. [x] English`, because some chat renderers split the checkbox and label
  onto separate lines.
- When the user replies to that flow with a numeric-only answer such as `1 2`,
  interpret the numbers against the most recent language checklist and apply the
  resulting ordered languages to the current step. Do not ask which languages the
  numbers mean when the checklist was just shown.
- Treat `gi commit language`, `gi коммит язык`, `ги коммит язык`, and older
  `gi язык коммита` forms as requests to configure commit-message languages in
  `tools/project-memory/git-preferences.json`.
- Treat `gi system language`, `gi систем язык`, and `ги систем язык` as
  requests to configure the agent's project working language in
  `tools/project-memory/system-preferences.json`.
- Follow `tools/project-memory/system-preferences.json` for progress updates,
  final answers, clarifying questions, user-facing explanations, and
  agent-created task artifacts. Do not use it to rewrite existing task text,
  code, commands, logs, quoted text, or a response language the user explicitly
  requested for a specific message.
- Launch applications in the background so focus does not jump away from the
  user's current window.
- After implementing a frontend, backend, API, or full-stack feature, restart
  the affected dev server or backend process when local run instructions provide
  a restart command or hot reload is uncertain. Then refresh the browser,
  client, or API caller before verification so checks do not use stale HTML,
  JavaScript, routes, schemas, or cached responses.
- Follow the copied `general-instructions` instruction kit for the full set of
  rules. In this project, use `AGENTS.md`, `tools/AGENT_WORKING_AGREEMENTS.md`,
  `tools/AGENT_RUNBOOK.md`, `tools/agent-start.ps1`, and project memory as the
  local authoritative sources.
- Treat shared-library files such as `COMMANDS.md` and `patterns/*.md` as
  upstream source material only when checking or applying accepted instruction
  kit updates; do not assume they exist locally in this project.
- When local project rules conflict with shared instructions, the local
  `AGENTS.md`, runbook, and working agreements take precedence.
