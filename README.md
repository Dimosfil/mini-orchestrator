# Mini Orchestrator

Mini Orchestrator is a small local workspace for experimenting with
AI-agent workflows. The current UI exposes the project dispatcher flow:

- create a chat-gated planner proposal
- explicitly approve the proposal
- run the selected dispatcher chain preset through real workers
- inspect agent stages, worker debug metadata, logs, and raw JSON

`planner -> executor -> reviewer` is the default example preset, not a static
workflow. Saved presets can contain any approved number of configured agents and
stages.

The dashboard has two confirmed execution modes:

- **Dispatcher** runs the selected preset through Mini Orchestrator's Codex
  dispatcher.
- **Symphony** can run the selected preset through contract-gated
  `mini-orchestrator.symphony-intake.v1` payloads. The production business flow
  keeps Mini Orchestrator as the task-card/checklist/chain owner: Mini sends
  one next-agent handoff at a time, waits for Symphony's retained result, then
  sends the following agent with previous outputs as context. The compatibility
  payload can still describe one `agentTasks[]` item per configured preset
  agent.

The older Campaign Concept Studio page has been replaced by the orchestrator
dashboard.

`launch-desk/` is retained as a legacy/experimental app. It is not part of the
active mini-orchestrator runtime unless explicitly promoted later.

## Install

```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1
python -m pip install -e .
```

## Run

```powershell
python -m mini_orchestrator --ui
```

Optional flags:

- `--host` expected host; must match config-service
- `--port` expected port; must match config-service
- `--open-browser`

The UI is a web-facing application, so startup follows GI config-service rules.
Before binding a port it reads the configured GI config-service URL, verifies
the service is reachable, then resolves its own service record:

```text
GET /services/mini-orchestrator
```

The host and port come from that record's `baseUrl`. If config-service is
unavailable, the `mini-orchestrator` record is missing, or the record lacks
`baseUrl`, `endpoints.availability`, or `endpoints.api`, startup stops with a
clear blocker instead of guessing a fallback port.

The project-local runtime selector is:

```text
tools/project-memory/service-runtime.json
```

The running UI exposes service-owned agent endpoints for future records:

- `GET /agent/guide`
- `GET /agent/contract`

Starting the UI also requires the `symphony` service to be available for Live
Runs Combined/Symphony views. Resolve the `symphony` service record through GI
config-service, check its `endpoints.availability` endpoint, and if it is down
start Symphony with the service record startup command before reporting the
Mini Orchestrator startup as complete.

## UI Workflow

Use a command such as:

```text
оркестратор план Сделай калькулятор
```

Click **План** to run dispatcher plan preview mode. The default UI mode calls
the real planner worker:

```powershell
python tools\codex-dispatcher\dispatcher.py --task "<command>" --plan-only
```

Real planner preview returns structured API errors when Codex app-server or the
selected model is unavailable.

The **Tech** tab shows a compact dispatcher debug summary for plan previews and
approved runs: runtime, log path, dispatch decision, worker thread/turn ids,
timings, event counts, Codex notification counts, and recent compact events.
Full prompts and outputs are not duplicated in the tech summary; use the log
path for deeper replay when needed.

Codex worker chats are grouped under the configured technical workspace
`workerChatRoot` from `tools/project-memory/service-runtime.json`. For this
project that path is `D:/AI/orchestrator-worker-chats`, so UI-spawned worker
threads should appear in Codex under that project instead of `mini-orchestrator`.
The worker turn still receives the real `mini-orchestrator` workspace as its
target cwd; the **Tech** tab shows both paths.

After review, check **План подтвержден** and click **Запустить workflow**. The UI
calls:

```powershell
python tools\codex-dispatcher\dispatcher.py --task "<command>" --chain
```

The approved workflow runs the selected release dispatcher chain preset through
Codex app-server. Local demo project generation is no longer part of the active
dispatcher surface.

For a real `gi test`, do not call the dispatcher CLI directly. Use the
project-local GI runner so the saved dashboard settings are honored:

```powershell
python tools\run_gi_test.py --task "<release/full-system test task>"
```

The runner preserves saved presets and current run settings, clears temporary
runtime state, reads the selected chain/execution mode from Mini Orchestrator,
and then calls either `/api/dispatcher/run` or `/api/symphony/runs`.

## Core Orchestrator

The **Core run** button sends the textarea content to the package-native
orchestrator:

```powershell
python -m mini_orchestrator "search AGENTS"
```

This path uses the `plan -> execute -> validate` loop in `mini_orchestrator/`.
The LLM coordinator is optional and falls back to rules unless OpenAI is
configured.

## Agent Builder

Visual agent flows use a two-layer storage model: browser `localStorage` remains
the draft/import state, while named saved flows are persisted by the backend
through `/api/agent-flows`. Saved backend flows carry `id`, `version`,
`createdAt`, `updatedAt`, and validation metadata; they are not executable until
later validation and compile steps approve them.

The builder also includes an approval manifest panel. The user reviews the task
summary, selected flow, agent order, model/reasoning/access settings, workspace
policy, and first prompt summary, then explicitly checks approval before the UI
creates an immutable manifest. Compiling the manifest does not launch workers.

Compiled manifests are validation artifacts until an approved Dispatcher or
Symphony workflow is started from the main dashboard. Live Runs renders the
approved workflow state: each task card shows status, last event, output
summary, selected chain, and reviewer verdict when present.

The WorkNest lifecycle bridge resolves the configured task manager through
config-service at use time, reads the WorkNest contract before state-changing
calls, and only exposes the documented external-agent operations:
`next-task` claim and terminal `task-completed` reporting.

The **Настройка агентов** page keeps browser `localStorage` as a draft/cache
layer for the currently open canvas. Important project-owned data is persisted
through the backend SQLite runtime store.

Agent chains are project-owned presets stored in
`.mini_orchestrator/runtime.sqlite3` and exposed through
`/api/agent-chain-presets`. The builder includes a default
`planner -> executor -> reviewer` example chain in the chain dropdown, and
saving the current canvas asks for a chain name so the visible cards and
connections can be reused later as a named preset. Browser-local presets are
imported into the backend on page load, then `localStorage` is only a cache and
migration fallback. The default chain is not a fixed workflow; saved presets may
contain any approved number of configured agents and stages.

Runtime state is stored in SQLite at `.mini_orchestrator/runtime.sqlite3`.
`.mini_orchestrator/test-runs/` remains file-based for generated runnable
artifacts. Other runtime themes such as saved flows, manifests, dispatcher
tasks, process output, agent cards, agent chain presets, worker profiles, and
Symphony gateway state belong in the SQLite store. Import legacy runtime files
with:

```powershell
python tools\migrate_runtime_to_sqlite.py
```

Use `--prune-files` after a successful import to remove migrated non-`test-runs`
files.

The main dashboard task form has an **Исполнительная цепочка** dropdown backed
by the same presets. Starting an approved workflow records the selected chain in
the run log, stores the executable chain preset in SQLite, and runs Codex
workers from that preset's agent order, `llm`, `reasoning`, `accessMode`, and
work-package fields. Executable presets must include each agent's selected
`llm`; missing models are rejected instead of filled from role defaults. Live
Runs shows the selected chain inside the single task card while the task is in
progress.

Live Runs has explicit source modes: **Combined**, **Dispatcher**, and
**Symphony**. Combined is the default and shows dispatcher/local run state plus
read-only Symphony daemon state. Dispatcher mode shows approved dispatcher JSONL
workflow replay. Symphony mode shows the read-only Symphony daemon bridge and
Mini-owned Symphony gateway runs. By default Mini Orchestrator resolves the `symphony`
service through GI config-service and reads its `endpoints.availability` /
`/api/v1/state` endpoint. Override the service id with
`MINI_ORCHESTRATOR_SYMPHONY_SERVICE_ID`, or set
`MINI_ORCHESTRATOR_DAEMON_STATE_URL` for an explicit manual state URL. In
Combined mode, empty or unavailable Symphony state never hides dispatcher-chain
runs; the dashboard keeps dispatcher cards visible and shows the Symphony error
in the source line.

Operational startup should keep this view live: when Mini Orchestrator is
started or restarted, Symphony must also be started or verified from its
config-service record. A running UI with unavailable Symphony is an incomplete
startup, not a successful full dashboard startup.

Old incomplete dispatcher JSONL runs are marked `stale` when their process is
gone or the log has not updated past
`MINI_ORCHESTRATOR_DISPATCHER_STALE_AFTER_SECONDS` (default 15 minutes). Stale
runs leave the active count and appear in Human Review with the stale reason.

`POST /api/symphony/runs` is a local Symphony gateway endpoint. It requires
approved task-run payloads and checks that Symphony observability is live. In
`orchestrationMode=mini-owned-chain` / `waitForCompletion=true`, Mini keeps
ownership of the task card, checklist, and preset handoff order, then posts one
next-agent `agentTasks[]` item at a time to `endpoints.taskIntake`,
`endpoints.agentIntake`, or `endpoints.intake` when documented. Compatibility
mode can still describe the full selected preset in one payload. If the service
record/contract does not expose intake, Mini records a visible blocked gateway
run with the normalized payload and the concrete blocker. The supported
upstream Symphony operations without intake remain observability/control only:
`GET /api/daemon/runs?source=symphony`, `POST /api/symphony/refresh`, and
`GET /api/symphony/issues/{issueIdentifier}`.

Mini-owned Symphony chains treat `timeoutPerStepSeconds` as a soft per-handoff
timeout. If the accepted issue is still running, `lateCompletionGraceSeconds`
keeps polling before cutting the chain so long executor stages can finish and
the next QA/Risk/PM handoff can continue.

Mini sends `symphonyWorkerMode` with Symphony runs. The dashboard default is
`debug-new-worker`, which asks Symphony to create a fresh inspectable
worker/agent monitor for each Mini-owned handoff. `optimal-reuse-idle` permits
compatible IDLE worker reuse for normal efficient operation.

Mini chat requests call the application backend, which routes the message
through `tools\codex-dispatcher\dispatcher.py` in real Codex app-server mode
with the card's selected model. Cards set to `rules` do not call a live LLM.

The builder is only a constructor for agent cards and chain presets. It saves
the selected chain preset for later use; task execution belongs in the main
dashboard/Kanban workflow, where the user chooses which chain preset should run
the task through Live Runs.

Completed agent runs appear in **Human Review** first. The user chooses
**ToDone** to accept the result into final Done, or **Доработки** to mark that
the task needs another pass. Dispatcher JSONL and Symphony gateway runs keep
the dashboard-local review bridge until a task-manager state-transition endpoint
exists.

WorkNest remains the task source and terminal completion sink. The local
WorkNest completion API accepts terminal `done` only after explicit user
acceptance (`reviewDecision=done` or `accepted=true`); blocked completion is
reserved for unrecoverable blocked results.

## LLM Configuration

- `OPENAI_API_KEY`
- `MINI_ORCHESTRATOR_LLM_PROVIDER` (`auto`, `openai`, `rules`, `off`)
- `MINI_ORCHESTRATOR_COORDINATOR_MODEL`
- `MINI_ORCHESTRATOR_EXECUTOR_MODEL`
- `MINI_ORCHESTRATOR_OPENAI_BASE_URL`
- `MINI_ORCHESTRATOR_DAEMON_STATE_URL`
- `MINI_ORCHESTRATOR_SYMPHONY_SERVICE_ID`
- `MINI_ORCHESTRATOR_DISPATCHER_STALE_AFTER_SECONDS`

## API Endpoints

- `GET /health` - health check
- `GET /agent/guide` - agent-facing service guide
- `GET /agent/contract` - strict service contract
- `POST /api/run` - package-native orchestrator JSON workflow run
- `POST /api/dispatcher/plan` - dispatcher plan preview
- `POST /api/dispatcher/run` - approved local dispatcher workflow
- `POST /api/agents/chat` - one-card mini chat through the selected model
- `GET /api/agents/default-card` - load the temporary default visual agent card
- `POST /api/agents/compile` - compile one visual card into a worker profile
- `POST /api/agents/run` - run one approved selected visual card
- `GET /api/agent-flows` - list saved backend flow drafts
- `POST /api/agent-flows` - create a saved backend flow draft
- `GET /api/agent-flows/{id}` - read a saved backend flow with validation metadata
- `PUT /api/agent-flows/{id}` - replace a saved backend flow and increment its version
- `POST /api/agent-flows/{id}/validate` - validate graph/runtime settings and return field-path errors
- `POST /api/agent-flows/{id}/compile` - compile a valid approved flow into an immutable run manifest
- `GET /api/agent-chain-presets` - list project-owned chain presets
- `POST /api/agent-chain-presets/import` - import browser-local preset arrays into SQLite
- `PUT /api/agent-chain-presets/{id}` - create or replace one project-owned chain preset
- `DELETE /api/agent-chain-presets/{id}` - remove one non-default chain preset
- `GET /api/daemon/runs?source=combined|dispatcher|symphony` - normalized read-only Live Runs state
- `POST /api/symphony/runs` - validates approved Symphony run intake, can run a Mini-owned sequential handoff chain one agent at a time, submits to documented Symphony intake, or records a blocked gateway run
- `POST /api/symphony/refresh` - config-service-resolved Symphony observability refresh
- `GET /api/symphony/issues/{issueIdentifier}` - config-service-resolved Symphony issue runtime/debug details
- `POST /api/worknest/claim` - contract-gated WorkNest `next-task` claim
- `POST /api/worknest/complete` - contract-gated WorkNest terminal `done` or `blocked` completion

Plan preview request:

```json
{
  "task": "оркестратор план Сделай калькулятор",
  "mode": "real"
}
```

Approved run request:

```json
{
  "task": "оркестратор план Сделай калькулятор",
  "approved": true
}
```

## Checks

```powershell
python -m compileall mini_orchestrator tools\codex-dispatcher
python -m pytest tests
python tools\run_gi_test.py --task "orchestrator plan Smoke sprint7"
python -m mini_orchestrator "search AGENTS" --no-log
```
