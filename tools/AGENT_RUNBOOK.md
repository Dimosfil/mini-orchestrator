# Agent Runbook

Every command should be copy-pasteable from the project root.

## Install

```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1
python -m pip install -e .
```

## Run

```powershell
python -m mini_orchestrator "прочитай AGENTS.md"
```

For the web UI, start from the config-service-resolved Mini Orchestrator
service record:

```powershell
python -m mini_orchestrator --ui
```

Also resolve the `symphony` service record through GI config-service, start
Symphony with its recorded startup command when it is not already healthy, and
verify its availability endpoint before treating the dashboard startup as
complete.

## Test

Before a fresh `gi test`, run the project-local GI test runner. It clears
runtime database state, dispatcher JSONL run cards, logs, and generated runtime
artifacts while preserving saved chain presets, then runs the saved dashboard
chain/execution settings:

```powershell
python tools\run_gi_test.py --task "<release/full-system test task>"
```

Use `python tools\clear_runtime_task_state.py` only for cleanup diagnostics. Do
not use direct `tools\codex-dispatcher\dispatcher.py --chain` as a `gi test`
result because it bypasses the selected dashboard chain preset and execution
mode.

```powershell
python -m compileall mini_orchestrator tools\codex-dispatcher
python -m pytest tests
python -m mini_orchestrator "search AGENTS" --no-log
```

The dispatcher live-chain smoke is documented in `README.md`; run it only when
Codex app-server and the selected worker models are available.

Смоук живой dispatcher-chain описан в `README.md`; запускай его только когда
доступны Codex app-server и выбранные модели воркеров.

## Build

```powershell
# No build pipeline exists yet.
```

## Smoke Check

```powershell
Test-Path .\AGENTS.md
Test-Path .\tools\agent-start.ps1
Test-Path .\README.md
Test-Path .\tools\project-memory\service-runtime.json
```

Expected result:

```text
All commands return True.
```

## Logs

```powershell
tools\codex-dispatcher\runs\
.mini_orchestrator\runtime.sqlite3
```

Dispatcher JSONL runs are generated under `tools\codex-dispatcher\runs\`.
Application runtime state is stored in SQLite at `.mini_orchestrator\runtime.sqlite3`.
Both are runtime/generated state and should stay out of source commits unless a
specific debug artifact is explicitly requested.

Dispatcher JSONL-логи создаются в `tools\codex-dispatcher\runs\`. Runtime-состояние
приложения хранится в SQLite-файле `.mini_orchestrator\runtime.sqlite3`. Это
генерируемое состояние; не добавляй его в коммиты без явного запроса на
конкретный debug artifact.

## Environment Notes

- Active product surface: local AI-agent orchestration dashboard and CLI.
- The dashboard has Dispatcher and Symphony execution modes. Dispatcher runs
  approved chain presets through `tools\codex-dispatcher\dispatcher.py`; Symphony
  uses the local gateway and service-record/contract-gated handoff flow.
- UI startup must resolve the `mini-orchestrator` service through GI
  config-service before binding host/port. A complete dashboard startup also
  verifies the `symphony` service availability record.
- WorkNest integration is contract-gated through config-service and exposes
  external-agent claim/completion operations only.
- Canonical stack inventory:
  `tools/project-memory/specs/technology-stack.md`.
- Shared instruction kit source:
  `D:\AI\general-instructions`.

- Активная поверхность продукта: локальный dashboard и CLI для AI-agent
  orchestration.
- Dashboard поддерживает режимы Dispatcher и Symphony. Dispatcher запускает
  подтвержденные chain presets через `tools\codex-dispatcher\dispatcher.py`;
  Symphony использует локальный gateway и handoff-flow через service record и
  contract.
- UI перед bind host/port должен разрешить сервис `mini-orchestrator` через GI
  config-service. Полный старт dashboard также проверяет доступность сервиса
  `symphony`.
- Интеграция WorkNest проходит через config-service и контракт; доступны только
  внешние операции claim/completion для агента.
- Канонический stack inventory:
  `tools/project-memory/specs/technology-stack.md`.
- Источник shared instruction kit:
  `D:\AI\general-instructions`.
