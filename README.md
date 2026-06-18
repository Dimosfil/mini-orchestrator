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

Live Runs first tries the read-only Symphony daemon bridge. The local-dev
default state endpoint is `http://127.0.0.1:4000/api/v1/state`; override it with
`MINI_ORCHESTRATOR_DAEMON_STATE_URL` when the daemon runs elsewhere. If the
daemon is unavailable, the dashboard falls back to dispatcher JSONL replay and
shows the daemon error in the source line.

Mini chat requests call the application backend, which routes the message
through `tools\codex-dispatcher\dispatcher.py` in real Codex app-server mode
with the card's selected model. Cards set to `rules` do not call a live LLM.

The builder is only a constructor for agent cards and chain presets. It saves
the selected chain preset for later use; task execution belongs in the main
dashboard/Kanban workflow, where the user chooses which chain preset should run
the task through Live Runs.

Completed agent runs appear in **Human Review** first. The user chooses
**ToDone** to accept the result into final Done, or **Доработки** to mark that
the task needs another pass. This review choice is currently a dashboard-local
bridge until a task-manager state-transition endpoint exists.

## LLM Configuration

- `OPENAI_API_KEY`
- `MINI_ORCHESTRATOR_LLM_PROVIDER` (`auto`, `openai`, `rules`, `off`)
- `MINI_ORCHESTRATOR_COORDINATOR_MODEL`
- `MINI_ORCHESTRATOR_EXECUTOR_MODEL`
- `MINI_ORCHESTRATOR_OPENAI_BASE_URL`
- `MINI_ORCHESTRATOR_DAEMON_STATE_URL`

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
- `GET /api/daemon/runs` - normalized read-only Live Runs state from Symphony daemon or dispatcher fallback

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
python -m compileall mini_orchestrator
python tools\codex-dispatcher\test_dispatcher.py
python -m mini_orchestrator "search AGENTS" --no-log
```
