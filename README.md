# Mini Orchestrator

Mini Orchestrator is a small local workspace for experimenting with
AI-agent workflows. The current UI exposes the project dispatcher flow:

- create a chat-gated planner proposal
- explicitly approve the proposal
- run the real planner -> executor -> reviewer dispatcher chain
- inspect planner, executor, reviewer, worker debug metadata, logs, and raw JSON

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

Selecting **Dry-run smoke** uses the local parser/log fallback without starting
Codex app-server:

```powershell
python tools\codex-dispatcher\dispatcher.py --task "<command>" --plan-only --dry-run
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

The approved workflow runs the release dispatcher chain through Codex
app-server. Local demo project generation is no longer part of the active
dispatcher surface.

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

The first daemon runner slice is an in-process dry-run path for compiled
manifests. `POST /api/daemon/run` creates a local run state and replayable JSONL
event log under `.mini_orchestrator/daemon-runs/`; it can run one selected
profile or a linear manifest graph such as Planner -> Executor -> Reviewer. It
does not bind a new port or launch real Codex workers. A successful dry-run
lands in `review`, not final `done`, until the user accepts it.

Live Runs renders per-node state from daemon `nodeStates` and `flowArtifacts`:
each node shows status, last event, output summary, artifact id, and reviewer
verdict when present.

The WorkNest lifecycle bridge resolves the configured task manager through
config-service at use time, reads the WorkNest contract before state-changing
calls, and only exposes the documented external-agent operations:
`next-task` claim and terminal `task-completed` reporting.

The **Настройка агентов** page stores visual agent cards in browser
`localStorage`. Each card includes a mini chat for checking how that card talks
through its selected `llm`, `speed`, and `reasoning` settings.

Agent chains are browser-local presets. The builder includes a default
`planner -> executor -> reviewer` chain in the chain dropdown, and saving the
current canvas asks for a chain name so the visible cards and connections can be
reused later as a named preset.

The main dashboard task form has an **Исполнительная цепочка** dropdown backed
by the same presets. Starting an approved workflow records the selected chain in
the run log, and Live Runs shows it inside the single task card while the task
is in progress.

Live Runs has explicit source modes: **Combined**, **Dispatcher**, and
**Symphony**. Combined is the default and shows dispatcher/local run state plus
read-only Symphony daemon state. Dispatcher mode shows only local daemon dry-run
state and dispatcher JSONL replay. Symphony mode shows only the read-only
Symphony daemon bridge. The local-dev Symphony state endpoint is
`http://127.0.0.1:4000/api/v1/state`; override it with
`MINI_ORCHESTRATOR_DAEMON_STATE_URL` when the daemon runs elsewhere. In Combined
mode, empty or unavailable Symphony state never hides dispatcher-chain runs; the
dashboard keeps dispatcher cards visible and shows the Symphony error in the
source line.

Old incomplete dispatcher JSONL runs are marked `stale` when their process is
gone or the log has not updated past
`MINI_ORCHESTRATOR_DISPATCHER_STALE_AFTER_SECONDS` (default 15 minutes). Stale
runs leave the active count and appear in Human Review with the stale reason.

`POST /api/symphony/runs` is intentionally a blocker endpoint for now. It
validates approved task-run payloads and returns `symphony-intake-missing` until
Symphony exposes a documented config-service-resolved task-intake contract.

Mini chat requests call the application backend, which routes the message
through `tools\codex-dispatcher\dispatcher.py` in real Codex app-server mode
with the card's selected model. Cards set to `rules` do not call a live LLM.

The builder is only a constructor for agent cards and chain presets. It saves
the selected chain preset for later use; task execution belongs in the main
dashboard/Kanban workflow, where the user chooses which chain preset should run
the task through Live Runs.

Completed agent runs appear in **Human Review** first. The user chooses
**ToDone** to accept the result into final Done, or **Доработки** to mark that
the task needs another pass. Local compiled-flow daemon runs record this choice
durably through `/api/daemon/review`; dispatcher JSONL runs still keep the
dashboard-local review bridge until a task-manager state-transition endpoint
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
- `POST /api/daemon/run` - create a single-card daemon dry-run from an approved manifest
- `POST /api/daemon/review` - record a local daemon Human Review decision (`done` or `rework`)
- `GET /api/daemon/runs?source=combined|dispatcher|symphony` - normalized read-only Live Runs state
- `POST /api/symphony/runs` - validates approved Symphony run intake and returns a blocker until intake is documented
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
python tools\codex-dispatcher\dispatcher.py --task "orchestrator plan Smoke sprint7" --chain --dry-run
python -m mini_orchestrator "search AGENTS" --no-log
```
