# Mini Orchestrator

Mini Orchestrator is a small local workspace for experimenting with
AI-agent workflows. The current UI exposes the project dispatcher flow:

- create a chat-gated planner proposal
- explicitly approve the proposal
- run a bounded local demo workflow under `test-projects/`
- inspect planner, executor, reviewer, logs, and raw JSON

The older Campaign Concept Studio page has been replaced by the orchestrator
dashboard.

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

Click **План** to run dispatcher plan preview mode. The UI calls:

```powershell
python tools\codex-dispatcher\dispatcher.py --task "<command>" --plan-only --dry-run
```

After review, check **План подтвержден** and click **Запустить workflow**. The UI
calls:

```powershell
python tools\codex-dispatcher\dispatcher.py --task "<command>" --local-test-project
```

The approved local workflow currently supports managed demo projects such as the
calculator and construction-store CRM. Generated demo files stay under
`test-projects/`, which is ignored by git.

## Core Orchestrator

The **Core run** button sends the textarea content to the package-native
orchestrator:

```powershell
python -m mini_orchestrator "search AGENTS"
```

This path uses the `plan -> execute -> validate` loop in `mini_orchestrator/`.
The LLM coordinator is optional and falls back to rules unless OpenAI is
configured.

## Agent Builder Mini Chat

The **Настройка агентов** page stores visual agent cards in browser
`localStorage`. Each card includes a mini chat for checking how that card talks
through its selected `llm`, `speed`, and `reasoning` settings. The mini chat is
a test conversation only; it does not execute the saved visual flow.

Mini chat requests call the application backend, which routes the message
through `tools\codex-dispatcher\dispatcher.py` in real Codex app-server mode
with the card's selected model. Cards set to `rules` do not call a live LLM.

## LLM Configuration

- `OPENAI_API_KEY`
- `MINI_ORCHESTRATOR_LLM_PROVIDER` (`auto`, `openai`, `rules`, `off`)
- `MINI_ORCHESTRATOR_COORDINATOR_MODEL`
- `MINI_ORCHESTRATOR_EXECUTOR_MODEL`
- `MINI_ORCHESTRATOR_OPENAI_BASE_URL`

## API Endpoints

- `GET /health` - health check
- `GET /agent/guide` - agent-facing service guide
- `GET /agent/contract` - strict service contract
- `POST /api/run` - package-native orchestrator JSON workflow run
- `POST /api/dispatcher/plan` - dispatcher plan preview
- `POST /api/dispatcher/run` - approved local dispatcher workflow
- `POST /api/agents/chat` - one-card mini chat through the selected model

Plan preview request:

```json
{
  "task": "оркестратор план Сделай калькулятор"
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
