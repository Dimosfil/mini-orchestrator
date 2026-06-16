# Handoff Summary: Codex-native orchestrator sprint

Date: 2026-06-16 15:59:05

## Goal

Build the first Codex-native orchestration layer for `mini-orchestrator`: a
dispatcher that can coordinate multiple Codex agents with different models,
record event logs, and use WorkNest as the task lifecycle manager.

## Implemented

- Added project-local task-manager selection:
  - `tools/project-memory/task-manager.json`
  - selected `service_id`: `worknest`
- Added Codex-native architecture plan:
  - `tools/project-memory/codex-native-orchestrator-plan.md`
- Added project-scoped Codex custom agents:
  - `.codex/agents/planner.toml`
  - `.codex/agents/executor.toml`
  - `.codex/agents/reviewer.toml`
- Added dispatcher prototype:
  - `tools/codex-dispatcher/dispatcher.py`
  - `tools/codex-dispatcher/README.md`
- Added dispatcher event protocol:
  - `tools/codex-dispatcher/EVENT_PROTOCOL.md`
  - `tools/codex-dispatcher/protocol.py`
- Added WorkNest lifecycle client:
  - `tools/codex-dispatcher/worknest.py`
- Updated local task checklist:
  - `tools/project-memory/pending-tasks.md`
- Updated ignored runtime output:
  - `.gitignore` ignores `tools/codex-dispatcher/runs/`

## WorkNest Sprint Status

- Config-service URL: `http://127.0.0.1:4100`
- WorkNest service id: `worknest`
- WorkNest API: `http://127.0.0.1:4187/agent-intake`
- Sprint:
  `2026-06-16_15-42-13_спринт-codex-native-orchestrator-mvp-sprint-codex-native-orchestrator-mvp`
- Sprint tasks completed through WorkNest manager API:
  - `001 Define Codex custom agents`
  - `002 Build Codex dispatcher prototype`
  - `003 Record orchestrator event protocol`
  - `004 Integrate WorkNest as task queue`
- Final WorkNest status: `archived`

## Checks Run

```powershell
python tools\codex-dispatcher\dispatcher.py --task "Smoke test dispatcher" --dry-run
python -m py_compile tools\codex-dispatcher\dispatcher.py
python tools\codex-dispatcher\dispatcher.py --task "Protocol smoke" --dry-run
python -m py_compile tools\codex-dispatcher\dispatcher.py tools\codex-dispatcher\protocol.py
python -m py_compile tools\codex-dispatcher\dispatcher.py tools\codex-dispatcher\protocol.py tools\codex-dispatcher\worknest.py
python tools\codex-dispatcher\dispatcher.py --task "WorkNest integration smoke" --dry-run
```

## Important Notes

- The dispatcher currently has a working `--dry-run` path.
- The real app-server path is scaffolded but has not yet been end-to-end tested
  with a live `codex app-server` run.
- WorkNest is used only as the task queue and lifecycle recorder. It is not an
  executor.
- Runtime dispatcher logs are generated under `tools/codex-dispatcher/runs/`
  and should remain ignored.

## Suggested Next Step

Run a real Codex app-server smoke test:

```powershell
python tools\codex-dispatcher\dispatcher.py --task "Plan the next smallest improvement to the dispatcher"
```

If that works, the next sprint should harden JSON-RPC event parsing and add a
small replay/status command for dispatcher runs.
