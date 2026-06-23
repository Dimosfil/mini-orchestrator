# Changelog

Accepted changes for the shared instruction library.

## 2026.06.23

- Clarified that `tools/project-memory/` is for durable specifications and
  compact evidence references, not raw work results. Generated outputs,
  screenshots, photos, crawled/downloaded files, logs, model outputs, build
  artifacts, export bundles, and run datasets should live in project-local
  artifact/evidence/output/data locations, with only manifests, summaries,
  checksums, or links kept in project memory when needed.

- Clarified `gi push` / `gi пуш` as a commit-then-push finish command. Agents
  must not reinterpret it as raw `git push`, a retry of a previous terminal
  push, or push-only behavior; if there are no scoped changes to commit, they
  report that instead. Push-only behavior is reserved for `gi only push` /
  `gi только пуш`.

- Hardened `gi test` as a live full-system verification command. Dry-runs,
  simulations, dispatcher-only runs, log replays, mock-only checks, and
  compile/unit-only checks must not be run for `gi test` unless the user
  explicitly asks for that diagnostic mode; they must never be reported as a
  passed `gi test`. If the documented live app/service/worker/UI system cannot
  be started or reached, agents must report the full test as blocked or not
  checked instead of substituting a dry-run.

- Added `gi test task` / `gi test` as release/full-system verification
  commands. `gi test task` records the user-selected workload for the next full
  project test, while `gi test` runs the current project's documented
  verification flow against that task. Agents must verify current local command
  contracts before running checks and must not treat old summaries, screenshots,
  demos, or previous completed runs as a substitute for a fresh requested test.

- Added `gi stack` / `ги стек` as a documented command for finding or building
  the current project's technology stack inventory. Agents first look for a
  visible canonical stack link or inventory in project-local instructions,
  README/docs/runbooks, or `tools/project-memory/specs/technology-stack.md`;
  when it is missing, they gather verified stack facts from current project
  evidence and add or request a top-level pointer according to local docs
  policy.

## 2026.06.21

- Modularized the runtime instruction entrypoint. Root and copied
  `AGENTS.md` files now stay compact and route agents to focused modules under
  `patterns/AGENTS_RUNTIME/`, preserving the previous behavior while reducing
  startup context and making task-specific rule retrieval faster.

- Added concrete-example abstraction guidance. Agents should extract the
  portable principle from a request, bug, screenshot, demo, or implementation
  detail before adding shared rules, and must not turn incidental entities,
  filenames, paths, years, queries, model names, UI labels, or selected runs
  into generic defaults, policies, architecture, or examples.

- Split project documentation from project memory. `README.md`, `docs/`, and
  runbooks should hold overview, user-visible functionality, stack, commands,
  operations, and troubleshooting; `tools/project-memory/` should hold
  implementation-driving algorithms, business rules, workflow contracts, state
  machines, invariants, architecture decisions, and verification guarantees.

- Added technology stack inventory guidance. GI-enabled projects should keep
  `tools/project-memory/specs/technology-stack.md` current with verified
  languages, runtimes, frameworks, package managers, build/test tools, storage,
  external services, commands, evidence paths, and open verification gaps.

- Added coherent batch verification guidance. Meaningful implementation,
  refactor, migration, and configuration cleanup batches must check
  source-of-truth consistency across touched layers, update durable
  project-memory specs when behavior or architecture changes, keep diffs scoped,
  and distinguish harmless line-ending warnings from real `git diff --check`
  errors.

- Extracted the accepted architecture and code-quality baseline into
  `patterns/ARCHITECTURE_AND_CODE_QUALITY.md`, with concise references from the
  live instructions and templates so consuming projects can copy the reusable
  module instead of carrying only inline guidance.

- Added `gi refactor` / `gi рефактор` / `ги рефактор` as a documented full
  project refactor command. Agents must refactor the current project according
  to all applicable GI rules, preserve user-visible behavior unless explicitly
  changed, plan and execute the work in verifiable batches, update durable
  project memory for meaningful architecture or workflow changes, and verify
  each affected area with documented checks.

- Added a code-quality baseline requiring agents to understand and apply OOP,
  SOLID, DRY, clean-code, maintainability, and extensibility principles where
  they fit the stack, while avoiding premature abstractions when duplication
  does not yet have a clear shared meaning.

- Clarified query/prompt normalization guidance as an
  interpretation/translation capability. Implementations may use deterministic
  resources, local algorithms, retrieval, services, or provider-swappable LLM
  adapters, but provider-specific calls and intent heuristics must stay behind
  interfaces rather than inside product/UI logic.

- Added query/prompt normalization boundary guidance. Translation maps, synonym
  dictionaries, prompt expansions, multilingual query handling, ranking
  thresholds, and model-specific search behavior should live in documented
  resources, config, adapters, or retrieval pipelines instead of inline
  application hard-code.

- Added project-agnostic explanation guidance for shared rules. Agents should
  not explain reusable GI rules by anchoring them to the current project, recent
  bug, demo, product name, or repository unless the user explicitly asks for
  that comparison; examples must be clearly illustrative and replaceable.

- Added development-tool/product boundary guidance. Orchestrators, task
  managers, agent harnesses, generators, scaffolding tools, and workflow logs
  must stay product-agnostic, treat generated products and selected runs as data,
  avoid demo/product hard-code, keep completed run logs compact, and follow
  SOLID or equivalent architecture boundaries with explicit contracts.

- Added `gi default` / `gi defaults` / `ги дефолт` as a documented clean-slate
  reset command. Agents must restore only documented project-owned first-run or
  default state, use local reset/cleanup/backup/run/test instructions, avoid
  deleting source files, project memory, instruction-kit files, user documents,
  production data, secrets, external service data, shared caches, sibling
  projects, or arbitrary user-home folders, and require explicit confirmation
  for irreversible or user-data-affecting resets.

## 2026.06.19

- Changed `gi reboot` / `gi restart` to start or restart all documented
  applications in the current project, not only one current app. Agents should
  use a local full-app-set start/restart command when documented; otherwise
  they should enumerate documented desktop apps, web/API apps, background
  workers, and similar runtimes, restart running ones, start missing ones, and
  verify each documented startup signal before reporting success.

- Clarified that `gi start sprint`, `gi sprint start`, and equivalent
  active-sprint wording are more specific than plain `gi start`. Agents must
  route them through the configured task-manager workflow, resolve the manager
  through config-service, follow the guide/contract, move work through documented
  lifecycle states, and stop with an exact blocker instead of returning only
  generic startup context or falling back to local notes, raw intake, guessed
  endpoints, or filesystem task edits.

- Tightened `gi reboot` / `gi restart` reporting so agents must identify the
  full documented app set before startup, account for each app by name or role,
  and verify each expected process, desktop window, web/API health endpoint, or
  worker signal. A web health check alone no longer permits a success report
  when an expected desktop app or other runtime was not launched or verified.

## 2026.06.18

- Defaulted missing unified `gi language` / `gi язык` selections to `1 2`
  (`English`, then `Russian`) for project working environment, commit messages,
  and tasks. Existing explicit language selections remain authoritative.

- Replaced Markdown task-list syntax for chat selection prompts with plain
  inline checkbox markers such as `[x] 1. English` and `[ ] 2. Russian`, because
  some chat clients render `- [x] 1. English` as a detached checkbox control
  followed by a separate label row.

- Tightened numbered Markdown checkbox guidance for language and task-manager
  prompts: every option must keep the checkbox marker, number, and label on one
  physical Markdown line, preventing standalone checkbox rows with detached
  numbered labels in chat renderers.

- Added connected-projects register guidance. Projects that depend on, research,
  vendor, or regularly interact with external repositories, services,
  libraries, docs sites, upstream tools, cloned examples, or sibling workspaces
  should record them in
  `tools/project-memory/specs/integration-contracts/connected-projects.md` with
  purpose, business/architecture role, local paths, Git/docs URLs, service or
  contract endpoints, owners, update commands, privacy/access boundaries,
  status, caveats, and the reason each dependency exists.

- Added machine-checkable RAG retrieval eval guidance and a local eval runner
  contract. `gi tools rebuild evals` / `gi rag rebuild evals` should verify RAG
  health, generated-ignore rules, count consistency across enabled retrieval
  layers, and expected source paths in top keyword, semantic, or hybrid results
  instead of treating free-form answer wording as the primary eval target.

- Added intent-preservation guidance for `gi summary` / `gi саммари`.
  Architecture and research handoffs, especially when the user evaluates an
  external project, article, pattern, or tool as a possible integration target,
  must explicitly preserve the user's exploration intent, map external concepts
  to current project components, and distinguish decisions from hypotheses.

- Tightened `gi summary` / `gi саммари` handoff structure: summaries should
  break the thread into meaningful topics, list and briefly describe key theses
  under each topic, add details only when a complex topic needs them, and link
  code files, URLs, media, images, logs, screenshots, or exact artifacts only
  when those references are necessary to understand or verify the context.

- Added resume/handoff reconciliation guidance: when the user asks where a
  previous thread stopped, agents must compare the handoff summary with the
  latest visible thread conclusion, screenshots, or direct quotes. The last
  explicit architectural/product decision, open question, or agreed next
  direction takes priority over incidental summary caveats. Unverified
  environment variables, skipped checks, and old next-step bullets must not
  become the active task unless the user selects them or they block the stated
  goal.

- Tightened `gi summary` / `gi саммари` handoff rules and the summary template
  so summaries preserve thread substance: user intent, decisions, code,
  architecture or business-logic changes, verification evidence, blockers, and
  next useful context. Routine command bookkeeping such as successful
  `gi push`, staging counts, git directives, branch/push metadata, and commit
  hashes should be omitted when git logs or command history can recover it. If
  a step-by-step protocol is needed, it should be written separately as
  `Thread Timeline`, not mixed into the ordinary handoff summary.

## 2026.06.17

- Replaced the active RAG rebuild command surface: `gi rebuild` / `ги ребилд`
  now means a current project/application rebuild only, such as producing a
  documented build artifact or exe. `gi tools rebuild` / `gi rag rebuild` /
  `ги тулс ребилд` / `ги раг ребилд` cover the separate GI/RAG-only rebuild flow
  and scoped node rebuilds. The old `root rebuild` wording is no longer part of
  the active command list.

- Tightened `gi reboot` / `gi restart` so agents must verify a real startup
  success signal after launch. A PID alone is not enough: agents should check
  the expected process after a short wait, visible desktop window when
  applicable, web/API health or discovery when applicable, and relevant startup
  or crash logs when documented, then report failed or unverified startup with
  concrete evidence.

- Updated config-service startup guidance so web-facing services with
  self-registration enabled can create or refresh their own service record when
  none exists. Services must first read the config-service guide and contract,
  choose a port that is free locally and absent from current config-service
  records, bind and health-check that port, then publish the actual bound port
  through the documented registration operation. Config-service must expose its
  own guide and contract for listing, reading, creating, updating, validating,
  and handling conflicts for service records.

## 2026.06.16

- Added Context7/external documentation retrieval guidance. Context7 may be
  used for current public library, framework, SDK, and API docs when configured
  or explicitly requested, but it must not replace project memory, service
  contracts, task managers, local source verification, or official OpenAI docs.
  Agents must avoid sending secrets, private code, private business rules, user
  data, or project-memory contents to external doc services without explicit
  private-source configuration and approval.

- Added `gi help` / `ги хелп` / `gi commands` / `ги команды` as an
  informational command that shows a compact GI command list with short
  descriptions. Added the command index to `COMMANDS.md` and clarified that
  help must not run startup restore, resume old work, call services, mutate
  files, or execute listed commands.

- Added `gi root rebuild` / `gi rag rebuild` / `ги рут ребилд` as a confirmed
  full project-memory/RAG rebuild command, plus node rebuild forms for SQL,
  chunks, vector, manifest, and evals. `gi обновить` must now inspect newly
  applied migrations for RAG-impacting changes and keep affected rebuild state
  stale until the documented rebuild and status checks succeed.

- Added portable project-memory specification guidance. `tools/summary/` is
  compact chat handoff state, while `tools/project-memory/` is durable product
  knowledge that should let another agent rebuild the same behavior on a
  different language, framework, platform, or UI stack. Non-trivial feature,
  business-rule, data-model, integration, and architecture work must update the
  relevant project-memory specification in the same scoped change. Added an
  architecture migration history template, `gi sql` / `gi vector` diagnostic
  command rules, and default activation limits for SQLite/FTS and vector
  retrieval.

- Clarified the project-memory/RAG split for exact graph facts versus semantic
  retrieval. SQLite or another structured store should hold deterministic paths,
  symbols, GUIDs, generated identifiers, asset links, reverse dependencies,
  commands, failures, and evidence-backed notes. Vector retrieval is a second
  semantic layer for conceptual search over curated notes, summaries,
  architecture docs, and selected chunks, and agents must verify current source
  files before editing because indexes can be stale.

- Added `gi first test` / `gi первый тест` / `ги первый тест` as a first-launch
  verification command. Agents must reset only documented project-owned app
  cache, generated state, temporary first-run profiles, and rebuildable local
  settings, then start the app and run documented first-launch smoke checks.

- Added verification-plan guidance that agents must confirm exact CLI flags,
  ports, routes, health endpoints, JSON payload fields, and environment
  variables from current project-local instructions, manifests, config, or
  source code before recommending or running smoke/API checks. Handoff
  summaries, screenshots, task notes, and old chat examples are status evidence,
  not authoritative command contracts.

- Clarified that `инит <source>` and `инит правила <source>` pointing to
  `general-instructions` are shared-instruction bootstrap/startup requests,
  never `git init`, folder creation, OpenCode setup, `npm init`, or
  `python -m venv`.

- Tightened `gi install` guidance so restore, dependency install, build, and
  tests are only prerequisites. Agents must run packaging and verify a current
  installer artifact before reporting installer success.

- Added an optional local Chroma adapter for semantic retrieval. The adapter
  builds a generated Chroma index from exported project-memory chunks and
  provides `rebuild`, `update`, `query`, `status`, and `clean` commands while
  keeping Chroma behind the retrieval-adapter boundary.

- Added semantic RAG retrieval guidance for embeddings, model metadata,
  collection versioning, chunk export, hybrid search, evals, and safety.
  Extended the project-memory indexer to create semantic-ready chunks and
  export them as generated JSONL for future Chroma, Qdrant, pgvector, or other
  vector adapters.

## 2026.06.11

- Added a unified, expandable RAG system structure that separates source
  corpus, manifests, chunk metadata, structured memory, retrieval adapters,
  context packets, observability, evals, and writeback. Added a project-local
  `rag-system.json` template and clarified that Chroma, Qdrant, pgvector, and
  similar tools should sit behind retrieval adapters rather than define the
  whole RAG system.

- Clarified GI's scope as agent-runtime neutral instructions for any compatible
  AI agent or assistant, not only Codex. Codex should be named only for
  Codex-specific tooling, surfaces, folders, or workflows.
- Clarified task-manager operations as routine sync/execution commands once the
  sprint/task content or workflow is known. Fast or weaker models may run them,
  but must follow config-service, guide/contract, documented payload, and
  readback steps exactly; they must not substitute project-memory notes, raw
  receipts, local checklists, guessed commands, or "tell me the exact command"
  fallbacks for manager API work.

- Clarified accepted rule propagation: RAG, startup, command, workflow, and
  agent-safety rules must be applied to the shared source repository itself and
  to consuming-project propagation artifacts, including templates, migrations,
  version/changelog, and local instruction-kit metadata.

- Clarified `gi manager`, `gi tm`, `gi manager test`, `ги менеджер`, and
  `ги манагер` handling: agents must inspect configured task managers through
  config-service by `service_id`, read guide/contract endpoints, and must not
  fall back to legacy `base_url`, stale memory, port scans, sibling projects,
  or guessed endpoints.

- Extended feature workflow contracts with a planning hierarchy for
  non-trivial features: feature idea, functional description, workflow
  contract, implementation plan, sprint breakdown, task breakdown, definitions
  of done, and verification. Clarified that tasks do not replace the feature
  contract because tasks say what to change while the contract says what
  behavior must remain true.

- Added feature workflow contract guidance: when a feature has an agreed
  runtime workflow, loading order, state machine, branching behavior,
  background work, or user-visible guarantee, agents should record it in
  project-local docs and read it before changing the feature. Added a copyable
  `FEATURE_WORKFLOW_CONTRACT` template.

- Added repository cleanup guidance: when preparing a project for GitHub or
  removing "unneeded" files, agents must not treat `AGENTS.md`, `tools/`,
  `tools/project-memory/`, `skills/`, bootstrap/update/deploy scripts, or
  agent-facing instruction/config files as removable solely because they look
  internal. Agents must inspect their purpose and preserve RAG/startup
  infrastructure unless the user explicitly confirms it is temporary.
- Clarified cleanup handling for SQLite/database files: generated agent-memory
  indexes should usually stay ignored and rebuildable, while reviewable docs,
  Markdown/JSON exports, schemas, and indexing scripts should be committed when
  useful. Databases containing secrets, private data, telemetry, task-manager
  state, absolute local paths, or conversation history must not be committed.

## 2026.06.09

- Added configuration-boundary guidance: deploy, user, runtime, machine,
  service, credential, filesystem, feature-flag, and operational-policy values
  must live in documented config, environment variables, or service discovery
  instead of application logic. Config-provided paths should be resolved and
  validated as absolute paths at application boundaries, and consuming projects
  should audit/refactor existing hard-coded values when applying the migration.

## 2026.06.08

- Added canonical source-repo guidance for instruction updates:
  `https://github.com/Dimosfil/general-instructions.git` is now the default
  shared-instruction source, while local folders are only checkouts/caches.
  Update tooling can clone or fetch that repo when no usable local checkout is
  available.

- Prefer relative shared-instruction-library paths, `GENERAL_INSTRUCTIONS_HOME`,
  or the current shared library over machine-specific absolute paths. Startup,
  update, bootstrap, and config-service guidance now avoid hard-coding
  one machine's shared-library location as a requirement.

## 2026.06.06

- Added agent-facing service guide guidance: HTTP services should publish
  `endpoints.guide` alongside `endpoints.contract`; agents read the guide first,
  then the contract, and stop on guide/contract mismatches instead of inferring
  permissions from stale memory, dashboard URLs, filesystem paths, or raw
  receipts.

- Added `gi add sprint` / `gi create sprint` / `gi добавить спринт` guidance:
  agents must create visible executable Sprints/Cycles through the configured
  manager contract, verify readback/lifecycle identifiers, and stop on
  auth/permission/schema/object-type blockers instead of downgrading to raw
  intake or Work Items. Clarified that external WorkNest agents use
  `/agent-intake/...` through config-service discovery while WorkNest owns
  internal Markdown files, status transitions, timing, archives, ordering, and
  task movement.
- Added active-task task-manager guidance: agents must get executable work
  through the configured manager contract, send progress/blocker/completion
  notes back to the manager, and stop on auth, permission, lifecycle, or object
  type mismatches instead of creating raw receipts, local notes, or substitute
  Work Items for requested Cycles/Sprints.
- Added Windows Codex tool setup guidance: prefer a trusted user-level
  `.codex\bin` directory, PowerShell-native HTTP commands, and narrow antivirus
  exclusions for Codex tool folders instead of broad System32 or PowerShell
  exclusions.
- Added a shared-instruction-library finish rule: when the user asks to add or
  accept a reusable rule, agents verify, commit, and push only the scoped rule
  changes, then run the `gi обновить` update flow when instruction-kit
  propagation applies.

## 2026.06.05

- Tightened config-service startup rules for web-facing applications: before
  binding any port, services must read their own startup/service record and
  neighboring service endpoints from a live config-service. If config-service is
  missing, unreachable, or incomplete, startup reports the blocker and waits
  instead of guessing or falling back to stale ports.

## 2026.05.30

- Clarified the WorkNest `next-task` endpoint contract as
  `GET /agent-intake/next-task?project=<project>&sprintId=<sprintId>` and told
  agents to re-read adapter endpoint docs before working around unexpected
  task-manager method or parameter errors.

## 2026.05.29

- Added explicit FTP command aliases: `gi ftp push` / `ги фтп пуш` for uploading
  configured build output, and `gi ftp folder` / `ги фтп папка` for choosing or
  updating the remote upload folder without uploading.
- Added `gi ftp service` / `ги фтп сервис` for manually registering, inspecting,
  or selecting FTP/FTPS/SFTP service records through config-service. Project
  agents now resolve FTP-capable services from config-service before asking for
  host details, and use numbered Markdown checkboxes when several services are
  available.
- Clarified config-service startup behavior: only web-facing projects should
  self-register; on startup they check their own `service_id`, create a missing
  record with the current port and endpoints, and refresh changed records.
- Added `gi ftp config` / `ги фтп конфиг` for project-local FTP/SFTP config
  setup in `tools/deploy/ftp.local.json`, plus `gi ftp` / `ги фтп` for uploading
  the configured build output to FTP, FTPS, or SFTP without exposing secrets.

## 2026.05.28

- Added encoding-safety guidance for agents: avoid PowerShell whole-file
  rewrites without explicit known encodings, prefer small patches or explicit
  UTF-8 APIs, and stop/restore if non-ASCII text turns into mojibake.
- Render language selection choices as task-list bullets such as
  `- [x] 1. English` instead of ordered-task syntax, so chat renderers keep
  checkboxes and labels on the same line while numeric replies still work.
- Added `gi config service on/off` as the current application's
  config-service self-registration flag, separate from
  `gi config service url=<url>`; enabling self-registration now requires an
  existing config-service URL or an explicit prompt to set one first.
- Added `gi reboot` / `ги ребут` as a start-or-restart command for the current
  application through project-local run instructions.
- Added a startup rule for applications that self-register in config-service:
  check the current config-service config on every process startup before
  publishing or refreshing the app's own service record, with cached config only
  as an explicitly documented degraded-startup fallback.
- Added a reviewable project-memory README and stdlib SQLite index helper for
  rebuilding a local searchable index from git tracked text files.

## 2026.05.27

- Restored numbered checklist handling for the unified `gi language` /
  `gi язык` flow, so replies like `1 2` are interpreted against the most recent
  language checklist during the three-step setup.
- Added unified `gi language` / `gi язык` language selection with separate
  ordered choices for project working environment, commit messages, and tasks.
- Added `gi config service` / `ги конфиг сервис` as explicit config-service
  discovery aliases, with `url=<url>` / `урл=<url>` forms for declaring the
  canonical config-service URL used by local services.
- Changed task-manager discovery guidance so project memory stores only the
  manager name or `service_id`; runtime URLs are resolved through
  config-service and the target service contract.

## 2026.05.21

- Added bare shared-instruction init aliases for
  `https://github.com/Dimosfil/general-instructions.git`:
  `инит`, `init`, and `инициализируй` now mean GI bootstrap/startup instead of
  Git initialization, OpenCode setup, project creation, agent creation, or skill
  creation.
- Added `patterns/MODEL_ROUTING_AND_COST_CONTROL.md` for agent applications
  that route requests across templates, fast models, tool-capable models, RAG,
  and reasoning models while controlling context, caching, budgets, and safety.
- Added versioning requirements for `gi install`: agents resolve the
  application version from project-local metadata and update build output,
  installer metadata, and installer filename or artifact naming when local
  tooling supports it.
- Added `gi install` / `gi инсталл` / `ги инсталл` as a build-and-installer
  command. By default agents use Inno Setup; when the user names another
  program after the command, agents use that program as the preferred packaging
  tool.

## 2026.05.20

- Made the instruction-kit update helper singleton-safe when counting pending
  migrations, so strict PowerShell mode handles zero, one, or many pending
  migration files consistently.
- Added `gi пул` / `gi pull` / `ги пул` as a current-branch fetch-and-pull
  command with cautious conflict handling: resolve only obvious low-risk
  conflicts, preserve user changes, and ask the user when product judgment or
  uncertainty is involved.
- Added project system-language preferences: `gi system language`, `gi систем
  язык`, and `ги систем язык` configure the agent's user-facing working
  language separately from commit-message language preferences. `gi commit
  language`, `gi коммит язык`, and `ги коммит язык` remain the commit-language
  command family.
- Clarified WorkNest sprint-plan intake: agents must not send `kind:
  sprint-plan` as `type: raw` and treat the receipt as an executable sprint;
  they must verify `/agent-intake/contract`, use a documented executable plan
  payload, or stop with a contract mismatch.
- Added bug-evidence intake guidance: screenshots, logs, pasted errors, or
  other bug reports trigger analysis and a follow-up question before edits,
  unless the user explicitly says `fix`, `почини`, or `gi почини`.
- Added `gi manager test` / `gi tm test` / `gi манагер тест` as an end-to-end
  task-manager lifecycle check: create a disposable no-op task, load/read it,
  take it in work when supported, complete it as `done`, read final status, and
  report any missing manager capability.
- Added fresh-runtime verification guidance: after frontend, backend, API, or
  full-stack feature changes, restart the affected dev server or backend process
  when local run instructions provide a restart command or hot reload is
  uncertain, then refresh the browser, client, or API caller before checking
  behavior.
- Clarified that changed API endpoints or route contracts should be probed after
  restart when they feed the UI, and skipped restarts or refreshes should be
  reported with a reason.

## 2026.05.19

- Added minimal no-op handling for greetings, thanks, acknowledgements, and
  status-neutral messages: agents should not run startup restore or read project
  files unless the message includes a task, path, command, error, or project
  question.
- Tightened compact restore guidance for `gi start`, `gi restore`, and
  title-only first messages: read only enough orientation for the next turn and
  avoid full summaries, runbooks, memory notes, logs, or diffs until a concrete
  task needs them.
- Clarified cached-context token economy: treat `cached input` as a symptom,
  optimize for smaller total live context, prefer compact summaries over long
  investigation history, start new sessions for unrelated tasks, and split R&D
  when later steps do not need the full prior reasoning trace.
- Added private local data guidance: agents must not read user-home app data,
  personal telemetry, `.codex`, `.cursor`, IDE logs, browser profiles, shell
  history, application SQLite databases, or app logs outside the project root
  without an explicit path and action from the user.
- Clarified that `apps.txt`, product plans, summaries, and task-manager notes
  are intent signals, not permission to inspect private local data sources.
- Clarified first-pass project study: agents should start from local
  instructions, README, manifests, and config entry points before recursive file
  mapping, and should treat nested checkouts or vendored trees as separate
  scope.
- Clarified that automatic chat UI tool counters are not agent progress updates,
  and agents should not duplicate them in prose.
- Added phase-level progress guidance: agents should not narrate after every
  command batch, report command counters, or live-blog intermediate hypotheses;
  updates should happen on phase changes, meaningful findings, blockers, or
  long quiet periods.
- Added a missing-entity fallback rule: when a required file, skill, config,
  script, endpoint, task, or other entity is absent, agents must reread relevant
  local instructions and accepted artifacts first, then ask the user if still
  unresolved, instead of using another project or shared library as a runtime
  fallback.
- Made `gi обновить` quiet by default: agents should avoid progress narration,
  broad command transcripts, and large reads during normal instruction-kit
  updates, then report only a compact result.
- Added a compact default output mode and optional verbose mode guidance for
  the update-check helper script.
- Added a strict project filesystem boundary: agents work inside the current
  project root and must not inspect or modify other project folders unless the
  user gives an explicit concrete path and action.
- Clarified that cross-project communication should use APIs, connectors, or
  task-manager endpoints, and that task-manager paths or metadata are not
  filesystem permission.
- Clarified task-manager role language: the agent takes and executes tasks
  through the manager, while the manager records, orders, assigns, and tracks
  task lifecycle metadata.
- Required sprint-work reports to avoid implying that the task manager performs
  implementation work.

## 2026.05.18

- Required task-manager adapters that accept single-task intake to either
  create executable lifecycle records, reject the payload with a clear contract
  error, or document it as intake-only.
- Clarified that agents must not create replacement one-task plans to work
  around raw task receipts that lack execution identifiers.
- Made instruction-kit update metadata recording explicit: project helper
  scripts should list pending migrations by default and use `-RecordApplied`
  only after file changes are applied and verified.
- Disabled metadata-only `-Apply` behavior in the update-check template to
  prevent projects from marking migrations applied before migrated file content
  exists.
- Clarified that task-manager configuration is project-local state and that
  `base_url` must be the manager API endpoint used for operations, not a UI URL
  unless an adapter explicitly documents that the same URL serves both UI and
  API.
- Added workflow-specific capability checks for task-manager operations so
  agents do not rely on generic health checks before posting plans or starting
  sprint work.
- Added guidance for projects to act as experience sources for `gi` by
  collecting reusable workflows, failure patterns, token-saving tactics, startup
  retrieval improvements, and instruction improvements as reviewable
  recommendations.
- Clarified that reusable project experience must include evidence and privacy
  review, and must not include secrets, private user data, production data, or
  unnecessary project-specific details.
- Clarified that the shared instruction-kit command prefix is always `gi`, not
  `GAI` or another alias, and that copied kits use `gi` as the local command
  surface in each project.
- Clarified that the main purpose of the copied instruction kit is token economy
  and RAG-style context restoration through local instructions, handoff
  summaries, targeted searches, accepted migrations, and project memory.
- Added optional `task-manager-plans` skill for reading and writing plans through
  configured task managers, with WorkNest as the first adapter.
- Added `gi tm` for checking connected task managers, updating local
  task-manager instructions, or choosing managers when none are configured.
- Clarified that `gi обновить` should immediately offer task-manager selection
  with numbered checkbox options when task-manager sync is newly available but
  not configured.
- Added `gi план` / `gi post plan` for sending the current work plan to a
  configured task manager.
- Clarified that WorkNest setup must fill `base_url` immediately and must not
  complete with `base_url: "TODO"`.
- Added WorkNest sprint workflow guidance for turning accepted plans into dated
  Markdown sprint folders with ordered task files.
- Added `gi старт` / `gi restore` as short commands for restoring project
  context after opening a new chat.
- Added `gi старт спринт` for restoring context, finding the active
  task-manager sprint, and executing ordered sprint tasks.
- Added short GI git finish commands: `gi пуш` for commit+push, `gi коммит` for
  commit only, `gi только пуш` for push only, and `gi коммит пуш` as an alias
  for commit+push.
- Clarified that ambiguous commit-language selection prompts should show
  numbered checklist options and explain that English is the required primary
  commit-message language.
- Added `gi тест-план` / `gi test plan` for project-aware test planning and
  feature verification.
- Added `patterns/PROJECT_TESTING_STRATEGY.md` and
  `templates/FEATURE_TEST_PLAN.template.md` for reusable project testing
  strategy.
- Added `gi гит-обзор` / `gi git summary` for summarizing the latest git commit
  in the current project without printing a full diff.

## 2026.05.16

- Clarified that `gi` means `general-instructions`, not `git`; missing `.git`
  must not stop instruction-kit updates and only disables the automatic
  commit/push step.
- Clarified that after a successful `gi обновить` / `gi обновись`, agents should
  commit and push the instruction-kit update changes when the current project is
  a git repository with a configured remote.
- Clarified that `gi` commands operate on the current project root and must not
  switch into another repository or the shared instruction library unless the
  user explicitly asks.
- Clarified that `gi` command responses must stay scoped to the shared
  instruction-kit command and must not resume an older product task unless the
  user explicitly asks.
- Made instruction-kit update checks tolerant of unavailable saved
  checkout/cache paths; agents should use the configured source repo, an
  explicit command URL, or ask for the shared instruction source instead of
  failing hard.
- Added `gi саммари` / `gi summary` as a short shared-instruction command that
  writes a handoff summary file under `tools/summary/` instead of only replying
  in chat.
- Clarified that ambiguous commit-message language selection prompts should use
  a concise Markdown checklist with current selections, not a prose-only list.
- Added the short `gi` chat-command prefix for shared instruction-kit commands,
  such as `gi обновись`,
  `gi init https://github.com/Dimosfil/general-instructions.git`, and
  `gi язык коммита: Russian`.
- Clarified that agents must not infer additional commit-message languages from
  the user's UI or message language; ambiguous requests should get a short
  clarification question.
- Clarified that reports about commit-language preference updates should mention
  `tools/project-memory/git-preferences.json` as a plain path, not a malformed
  placeholder markdown link.
- Added short user-facing agent prompts for bootstrapping, updating, restoring
  context, configuring commit-message languages, and requesting commits.
- Clarified that
  `Обновись из https://github.com/Dimosfil/general-instructions.git` is
  idempotent:
  bootstrap/init first when no local instruction kit exists, otherwise apply
  only pending migrations.
- Clarified that chat requests to configure commit-message languages should
  update `tools/project-memory/git-preferences.json` directly instead of only
  telling the user to run a PowerShell helper.
- Added instruction-kit migrations with `patterns/INSTRUCTION_KIT_MIGRATIONS.md`
  and accepted migration files under `migrations/`.
- Added `templates/check-instruction-kit-updates.template.ps1` for project-level
  update checks.
- Added `patterns/GIT_WORKFLOW.md` with explicit commit-request policy, dirty
  worktree handling, and commit-message language rules.
- Added project-local commit-message language preferences with English as the
  primary language and optional Russian, Spanish, German, or French additions.
- Added `templates/git-preferences.template.json` and
  `templates/select-git-commit-languages.template.ps1`.
- Updated startup restore to show the current commit-message language
  preferences and how to change them.
- Added the skill module concept, including `patterns/SKILL_MODULES.md` and
  `templates/SKILL.template.md`.
- Updated instruction-kit version parsing to support multiple releases on the
  same date.
- Renamed active project templates and copied project paths from tool-specific
  names to generic agent names.
- Updated startup, runbook, working-agreement, summary, checklist, bootstrap,
  and index guidance to use agent-neutral wording.
- Bumped copied instruction-kit provenance to `2026.05.16`.

## 2026.05.15

- Refactored `AGENTS.md` into focused sections for rule precedence, authoring,
  token economy, startup behavior, UI/focus, update intake, verification, and
  git policy.
- Added `patterns/FIRST_MESSAGE_HANDLING.md` for first-message title handling
  and shared-instruction bootstrap behavior.
- Reduced duplicated context-hygiene guidance in the development playbook and
  project templates.
- Generalized broad artifact guidance from zip archives to broad artifacts and
  full check matrices.
- Clarified PowerShell command examples and equivalent-command expectations for
  other shells.
- Added instruction-kit versioning artifacts for copied project instruction
  kits.
