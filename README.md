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

- `--host` (default `127.0.0.1`)
- `--port` (default `8765`)
- `--open-browser`

Then open `http://127.0.0.1:8765`.

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

## LLM Configuration

- `OPENAI_API_KEY`
- `MINI_ORCHESTRATOR_LLM_PROVIDER` (`auto`, `openai`, `rules`, `off`)
- `MINI_ORCHESTRATOR_COORDINATOR_MODEL`
- `MINI_ORCHESTRATOR_EXECUTOR_MODEL`
- `MINI_ORCHESTRATOR_OPENAI_BASE_URL`

## API Endpoints

- `GET /health` - health check
- `POST /api/run` - package-native orchestrator JSON workflow run
- `POST /api/dispatcher/plan` - dispatcher plan preview
- `POST /api/dispatcher/run` - approved local dispatcher workflow

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
