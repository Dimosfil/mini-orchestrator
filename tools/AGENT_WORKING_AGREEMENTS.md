# Agent Working Agreements

## Scope

- Keep changes small and tied to the current request.
- Ask before expanding into unrelated modules.
- If a task requires files outside the agreed working area, say so first.
- Treat the current project root as the filesystem boundary for normal work.
  Do not read, search, edit, create, delete, move, or inspect files in another
  project or arbitrary external folder unless the user gives an explicit
  concrete path and action. Use APIs, connectors, or task-manager endpoints for
  cross-project communication.
- `D:\AI\symphony\` is an explicitly approved external reference workspace for
  this project. Agents may read, search, inspect, and use it when designing or
  implementing Symphony-style orchestration in `mini-orchestrator`. Do not edit,
  delete, move, or commit files in that external workspace unless the user gives
  a separate explicit action for that path.
- Keep connected external projects in
  `tools/project-memory/specs/integration-contracts/connected-projects.md`.
  Read that register before touching integrations, nested repositories, cloned
  examples, or external project folders. Update it when adding, removing,
  replacing, relocating, or materially changing the role of a connected project.
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

## User Changes

- Do not revert user changes unless explicitly requested.
- Treat dirty worktrees as normal.
- If user changes affect the task, work with them.
- Preserve recorded feature workflow contracts. If a feature has an agreed
  runtime workflow, loading order, branching state flow, background work, or
  user-visible guarantee, read that contract before changing the feature and
  update it in the same scoped change when behavior intentionally changes.
- For non-trivial features, keep the feature idea, functional description,
  workflow contract, implementation plan, sprint breakdown, task breakdown,
  definitions of done, and verification connected. Tasks do not replace the
  feature contract.
- For non-trivial business-rule, data-model, integration, algorithm, or
  architecture work, update the relevant project-memory specification in the
  same scoped change so behavior can be rebuilt on another language, framework,
  or platform. A handoff summary is not a substitute.

## Git

- Default: the agent edits and verifies; the user reviews and commits.
- Treat `gi коммит`, `gi пуш`, `gi коммит пуш`, and `gi только пуш` as explicit
  git finish requests. `gi коммит` commits scoped current changes only; `gi пуш`
  and `gi коммит пуш` commit scoped current changes and push the current branch;
  `gi только пуш` pushes existing local commits without creating a new commit.
  Inspect status, keep unrelated/user changes out, follow commit-message
  preferences, and stop on ambiguous scope, missing remote, conflicts, secrets,
  or push failures.
- Treat `gi пул`, `gi pull`, and `ги пул` as explicit requests to fetch and pull
  the current branch from its configured upstream. Inspect status, branch, and
  upstream first. Resolve only obvious, low-risk conflicts where intent is clear
  and user changes are preserved; if product judgment, unrelated changes,
  secrets, or uncertainty are involved, stop and ask the user with concise
  options.
- Exception: after a successful `gi обновить` / `gi обновись`, commit and push
  only the resulting instruction-kit update changes when this project is a git
  repository with a configured remote. If unrelated/user changes, no remote,
  push failure, or conflicts are present, stop and explain the blocker.
- In a shared instruction-library project, a user request to add or accept a
  reusable rule is also an explicit finish request for that accepted rule:
  verify, commit, and push only the scoped rule changes, then run the
  `gi обновить` update flow when accepted instruction-kit propagation applies.
  Do not include unrelated dirty worktree changes or recurse merely because this
  finish rule itself was added or run.
- Branch naming: use `codex/` for agent-created branches unless the user asks
  for another name.
- Generated files policy: keep generated caches, logs, local databases, vector
  indexes, and runtime noise out of git; commit only reviewable source, docs,
  scripts, and config templates.
- Never commit secrets, credentials, local databases, logs, or caches.
- Follow `tools/project-memory/git-preferences.json` for commit-message
  languages. English is primary; selected additional languages are included when
  the user explicitly asks the agent to commit.
- When the user asks in chat to change commit-message languages, update
  `tools/project-memory/git-preferences.json` directly and summarize the new
  setting.
- Do not infer additional commit-message languages from the user's UI language
  or message language. If the requested languages are ambiguous, ask which
  additional languages to enable.
- For ambiguous commit-language selection, ask with a concise numbered Markdown
  checklist showing `English` as always selected and current additional
  languages as checked. Explain that `English` is the required primary
  commit-message language and cannot be disabled. Ask the user to reply with
  language names or numbers. Render each option as a plain inline checkbox
  marker, number, and label on one physical Markdown line, such as
  `[x] 1. English`; do not use Markdown task-list syntax such as
  `- [x] 1. English` or ordered-task syntax such as `1. [x] English`, because
  some chat renderers split the checkbox and label onto separate lines.
- When reporting this change, mention the plain
  `tools/project-memory/git-preferences.json` path instead of malformed or
  placeholder markdown links.
- If the user explicitly wants to configure languages manually, they can run:

```powershell
.\tools\select-git-commit-languages.ps1
```

or:

```powershell
.\tools\agent-start.ps1 -ConfigureGitCommitLanguages
```

## Agent Language

- Follow `tools/project-memory/system-preferences.json` for the agent's
  user-facing working language in this project.
- Apply the configured system or project language to progress updates, final
  answers, clarifying questions, user-facing explanations, agent-created task
  titles, task descriptions, task-manager updates, plans, and checklists.
- For task titles, descriptions, and task-manager updates, treat the first
  configured task language as the main language. If exactly one task language is
  configured, write task text only in that language. If multiple task languages
  are configured, write the main-language text first and then add one clear
  translation per additional language. Do not duplicate the same content twice
  in one language, and do not mix untranslated labels, templates, or Definition
  of Done text from another configured language into the main-language text.
- Do not apply the system or project language to existing task text, code,
  commands, logs, quoted text, or a response language the user explicitly
  requested for a specific message.
- Treat `gi language`, `gi язык`, `ги язык`, `gi project language`,
  `gi проект язык`, `ги проект язык`, `gi язык проекта`, and `ги язык проекта`
  as requests to configure three ordered language sequences: project working
  environment, commit messages, and tasks.
- If the unified project-language command does not include explicit languages,
  ask in three numbered steps. For each step, show a concise numbered Markdown
  checklist with the available languages and the current selection, or `English`
  then `Russian` checked when that surface has no current ordered selection.
  Render each option as a plain inline checkbox marker, number, and label on one
  physical Markdown line, such as `[x] 1. English`; do not use Markdown
  task-list syntax such as `- [x] 1. English` or ordered-task syntax such as
  `1. [x] English`. Then accept the user's next answer as numbers or language
  names for that step.
- If the user replies with only numbers, such as `1 2`, map them to the most
  recent checklist and preserve that order. Do not ask what those numbers mean
  after showing the checklist.
- Treat `gi system language`, `gi систем язык`, and `ги систем язык` as
  requests to configure this preference.
- Keep this setting separate from commit-message languages. `gi commit
  language`, `gi коммит язык`, `ги коммит язык`, and older `gi язык коммита`
  forms configure `tools/project-memory/git-preferences.json`, not the agent's
  working language. The unified project-language command updates both
  preference files.
- If the user explicitly wants to configure the system language manually, they
  can run:

```powershell
.\tools\select-system-language.ps1
```

or:

```powershell
.\tools\agent-start.ps1 -ConfigureSystemLanguage
```

## Context Hygiene

- Do not print full `git diff` output by default. Prefer `git diff --stat` and
  targeted queries for relevant files or patterns.
- For first-pass project study, read local instructions, README, manifests, and
  config entry points before building a file map. Use recursive scans only after
  a targeted search fails or the task clearly requires repository-wide
  inventory.
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
- Launch applications in the background so focus does not jump away from the
  user's current window.
- Treat a short first message as a possible chat title: restore context, then
  ask what to do next instead of executing the title as a task.
- Treat short chat commands that start with `gi` as shared instruction-kit
  commands for the copied `general-instructions` kit in this project. `gi` is
  the only short prefix; do not rename it to `GAI` or another alias.
  If a `gi` command is missing a needed parameter, ask one short clarification
  question instead of guessing.
- Treat `gi help`, `gi хелп`, `ги help`, `ги хелп`, `gi commands`,
  `gi команды`, and `ги команды` as informational requests for the local GI
  command list. Show compact command names and short descriptions; do not run
  startup restore, resume old tasks, call services, or execute the listed
  commands.
- Treat `оркестратор <task>` and `orchestrator <task>` as project-local
  mini-orchestrator dispatch commands. For early tests from chat, run
  `python tools\codex-dispatcher\dispatcher.py --task "<original command>" --chain --dry-run`
  unless the user explicitly asks to launch a real Codex worker. `оркестратор
  план <task>` / `orchestrator plan <task>` starts from a planner-directed
  task, `оркестратор исполнитель <task>` / `orchestrator executor <task>` starts
  from an executor-directed task, and `оркестратор ревью <task>` /
  `orchestrator review <task>` starts from a reviewer-directed task. In
  full-chain mode the dispatcher still runs planner -> executor -> reviewer.
  Use the low-level dispatcher without `--chain` only when the user asks for one
  selected worker.
- Use the instruction kit as a token-economy and RAG-startup layer: restore only
  task-relevant context from local instructions, summaries, targeted searches,
  and project memory instead of broad repository reads or large outputs.
- Use `gi sql` and `gi vector` as inspection commands for project-memory
  retrieval metrics and activation limits. Report current counts, readiness,
  staleness, and recommendations; do not deploy heavy databases or external
  services by default.
- Use `gi rebuild` for the current project/application rebuild only, such as
  producing an executable, package, or documented build artifact. Use
  `gi tools rebuild` / `gi rag rebuild` only for a confirmed full rebuild of
  the current project's configured GI/RAG project-memory retrieval system:
  source manifest, SQLite/FTS or structured memory indexes, chunk exports,
  vector indexes, adapter metadata, and retrieval eval/status checks. Use node
  forms such as `gi tools rebuild sql`, `gi tools rebuild chunks`,
  `gi tools rebuild vector`, and `gi tools rebuild evals` for scoped GI/RAG
  rebuilds. For an `evals` node, prefer machine-checkable retrieval checks that
  verify index health, count consistency, and expected source paths in top
  keyword, semantic, or hybrid results; do not treat an answer's wording as the
  primary eval target.
  During `gi обновить`, migrations that change RAG rules, indexers, chunking,
  embedding metadata, or retrieval adapters must leave affected rebuild state
  stale until the documented rebuild and status checks succeed.
- Keep `gi` command responses scoped to the shared instruction-kit command. Do
  not resume an older product task after a `gi` command unless the user
  explicitly asks.
- Run `gi` commands against this project root. Do not switch to another
  repository, the shared instruction library, or a path from an older task unless
  the user explicitly asks.
- Task-manager paths, raw intake metadata, summaries, or previous chat context
  are not permission to enter another project folder.
- `gi` means `general-instructions`, not `git`. Missing `.git` blocks only the
  automatic commit/push step after a successful GI update; it does not block
  checking or applying instruction-kit file updates.
- Treat `gi саммари` and `gi summary` as requests to write a handoff summary
  file under `tools/summary/`, not only as requests to summarize in chat.
- Keep handoff summaries focused on thread substance as a thematic handoff, not
  as a short chronological retelling. Break the thread into meaningful topic
  sections, list the key theses under each topic, and briefly describe each
  thesis. Preserve user intent, important decisions, code or architecture
  changes, business/product logic, verification evidence, blockers, and next
  useful context. For architecture or research threads about an external
  project, article, pattern, or tool as a possible integration target, preserve
  the integration intent, map external concepts to current project components,
  and separate decisions from hypotheses. Omit routine command bookkeeping,
  successful git/GI steps, branch names, push targets, and commit hashes unless
  repository state changes the next agent's work. When a detailed step-by-step
  protocol is needed, add a separate `Thread Timeline` section or file only
  when the user asks or the timeline materially helps the handoff.
- When asked where a previous thread stopped, compare the latest handoff summary
  with the most recent visible thread conclusion or user-provided evidence.
  Prefer the last explicit architectural/product decision, open question, or
  agreed next direction over incidental caveats in the summary. Do not turn an
  unverified caveat, environment variable, skipped check, or old `Next Best
  Steps` bullet into the current task unless the user selects it or it blocks
  the stated goal.
- Treat `gi гит-обзор` and `gi git summary` as requests to summarize the latest
  git commit in the current project in chat. Include commit metadata, changed
  files, compact stats, inferred purpose, and notable risks or checks. Do not
  print a full diff, create a summary file, commit, or push for this command.
- Treat `gi тест-план` and `gi test plan` as requests to inspect local project
  test commands and produce a compact verification plan for the current feature,
  bug fix, or release check. Plan first; run checks only when the user asks or
  when the current task already requires verification.
- For verification plans and smoke checks, confirm exact CLI flags, ports,
  routes, methods, JSON payload fields, and required environment variables from
  current local instructions, manifests, config, or source code. Summaries and
  old chat snippets are evidence, not authoritative command contracts.
- Treat `gi install`, `gi инсталл`, `ги инсталл`, and clear typo variants as
  build-and-installer requests. The task is complete only after the packaging
  command runs and a current installer artifact is produced or explicitly
  verified; restore/build/test alone are preliminary checks.
- Treat `gi reboot`, `ги ребут`, `gi restart`, and `ги рестарт` as requests to
  start or restart all documented applications in the current project. Before
  starting anything, identify the full project app set from local run
  instructions, manifests, service records, desktop packaging metadata, or
  project memory. Use a documented full-app-set start/restart command when one
  exists; otherwise enumerate and launch/restart each documented desktop app,
  web/API app, worker, or other runtime in the background. Verify each app's
  documented startup signal and report each app by name or role with
  started/restarted/skipped status and evidence. Do not report success from a
  PID alone, from a web health check alone, or while any expected app or worker
  is unlaunched or unverified.
- Treat `gi first test`, `gi первый тест`, and `ги первый тест` as first-launch
  verification requests. Reset only documented project-owned app cache,
  generated state, temporary first-run profiles, and rebuildable local settings;
  do not delete user documents, production data, secrets, credentials, shared
  system caches, sibling projects, or arbitrary user-home folders. If exact
  reset paths or commands are missing, ask one concise question instead of
  guessing.
- Treat `gi default`, `gi defaults`, and `ги дефолт` as default-state reset
  requests for the current project. Read project-local reset, cleanup,
  first-run, run, backup, and test instructions before clearing anything. Use
  only documented reset scripts, paths, keys, or contracts for rebuildable
  project-owned app state. Do not delete source files, project-memory
  specifications, instruction-kit files, user documents, production data,
  secrets, credentials, external service data, shared system caches, sibling
  projects, or arbitrary user-home folders. If reset targets are undocumented,
  ask one concise question instead of guessing; if a reset could remove
  user-owned data, stop for explicit confirmation. After reset, start the
  project through documented run instructions and report what was reset, what
  was left untouched, what passed, and any blocker.
- Treat `init <source>`, `инит <source>`, `инициализируй <source>`, and
  `инит правила <source>` as shared-instruction bootstrap/startup requests when
  `<source>` points to a known `general-instructions` source. Never reinterpret
  these forms as `git init`, folder creation, OpenCode setup, project creation,
  `npm init`, or `python -m venv` unless the user explicitly names that action.
- Treat a first message that points to a shared instruction library as an
  instruction bootstrap, not as a request to add that library as a dependency.
- If the user asks to update from a shared instruction library and this project
  has no `tools/project-memory/instruction-kit.json`, treat that as first-time
  instruction bootstrap/init.
- Run `gi обновить` quietly by default: do not narrate step-by-step reasoning,
  repeated progress, command transcripts, broad file reads, or full diffs during
  normal successful updates. Apply the update, then report a compact summary
  with versions, migration counts/IDs, changed files, checks, commit/push
  result, and blockers if any.
- For web applications, assume the user will inspect the UI manually. Do not
  open, browse, screenshot, or visually inspect the UI automatically unless the
  user explicitly asks for that.

## Editing

- Prefer patch-style edits for manual changes.
- Avoid unrelated formatting churn.
- Add comments only when they clarify non-obvious behavior.

## Task Planning

- For analysis, refactoring, migration, or multi-step implementation tasks,
  create or update a concise checklist in `tools/project-memory/pending-tasks.md`
  or a dedicated task plan in `tools/project-memory/` before editing code.
- Include the goal, planned changes, execution order, risks or dependencies, and
  verification steps.
- Update progress as meaningful steps complete.
- Keep plans concise. Do not store full diffs, large logs, generated outputs,
  secrets, credentials, or private production data.

## Shared Instruction Updates

- When this project reveals a reusable improvement to agent instructions,
  workflows, templates, or checklists, write a dated recommendation to the shared
  instruction library's `updates/` folder if it is available.
- If no shared instruction library is available, use a local intake folder such
  as `tools/instruction-updates/` or
  `tools/project-memory/instruction-updates/`.
- Treat recommendations as intake, not accepted rules.
- Recommendations should explain the observed problem, reusable rule or
  workflow, evidence paths, affected files or commands, risks, and privacy
  review.
- Capture reusable workflows, failure patterns, token-saving tactics, and
  agent-instruction improvements that could improve `gi` for other projects.
- Do not add a shared instruction library as a project dependency, package,
  submodule, symlink, or runtime reference unless the user explicitly asks for
  that.

## Architecture Boundaries

- Keep developer tools, orchestrators, task managers, agent harnesses, workflow
  UIs, scaffolding systems, and code generators separate from the products they
  build. Generated applications, demos, dashboards, bots, libraries, and sites
  are task data or outputs, not the tool's identity.
- Do not hard-code one demo, customer, project type, selected run, product name,
  UI label, folder slug, stack, or task contract as a runtime concept. Store
  product-specific choices in task payloads, manifests, fixtures, plugins,
  adapters, project-local configuration, service discovery, or user-selected
  state.
- Workflow/progress logs belong to the selected or active run. Detailed logs for
  completed runs should collapse by default or render as compact final status
  unless the user is debugging them.
- Keep query interpretation, translation, prompt expansion, and model-facing
  query creation in a dedicated capability. Preserve the original user query
  separately from interpreted intent and model-facing text.
- Keep provider-specific LLM calls, prompts, model names, budgets, fallbacks,
  timeouts, privacy policy, ranking weights, score thresholds, and compatibility
  hacks behind adapters, resources, configuration, services, or pipeline
  components with tests. Do not embed them in UI, request, command, or one-off
  feature logic.
- Build with clear code-quality boundaries: use OOP, SOLID, DRY, clean-code,
  maintainability, and extensibility principles where they fit the stack. In
  non-OOP stacks, apply the same separation through modules, functions,
  services, protocols, and data contracts.
- Prefer cohesive domain models, explicit interfaces at integration boundaries,
  dependency inversion for infrastructure, small composable modules, typed or
  validated contracts, low duplication, clear names, focused functions/classes,
  and established framework patterns. Avoid premature abstractions until
  duplication has a clear shared meaning.
- When documenting reusable GI rules, keep explanations project-agnostic. Use
  neutral terms and mark any concrete example as illustrative so the rule can be
  copied into an unrelated project without importing this project's incident or
  domain.

## Task Managers

- Treat task-manager configuration as project-local state.
- Store only the manager name or `service_id` plus non-secret project
  preferences in project memory.
- Resolve task-manager runtime URLs through GI config-service by service id;
  do not store, guess, or copy API endpoints from old notes or other projects.
- If a configured manager id is missing from config-service, stop with a concise
  blocker instead of falling back to port scans or stale task-manager memory.
- Before posting plans or starting sprint work, read the manager guide when
  present, then verify the workflow-specific manager contract and capabilities,
  not only generic health.
- For agent-facing HTTP services, treat `endpoints.guide` as service-owned
  onboarding and `endpoints.contract` as strict workflow validation. If the
  guide and contract disagree about endpoints, ownership, or permissions, stop
  and report the mismatch instead of inferring behavior from stale memory,
  filesystem paths, dashboard URLs, or raw receipts.
- Treat task managers as work queues and lifecycle recorders, not as the actors
  doing implementation work. The agent takes, implements, verifies, and reports
  tasks through the manager.
- For single-task intake, require executable lifecycle identifiers, a clear
  rejection, or explicit intake-only documentation. Do not create replacement
  one-task plans to work around raw task receipts that cannot be advanced
  through lifecycle endpoints.

## Verification

- Reread edited files after changes.
- Run the fastest relevant check first.
- Record checks run and failures in the handoff summary.

## Processes

- Ask before closing editors, apps, servers, or other visible processes.
- Launch GUI tools quietly in the background when possible.
