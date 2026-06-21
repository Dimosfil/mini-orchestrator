# Technology Stack

Last reviewed: 2026-06-21

## Summary

- Primary stack: Python package and stdlib-served web UI.
- Runtime model: local AI-agent orchestration tool with CLI, HTTP dashboard,
  dispatcher subprocesses, SQLite runtime state, and config-service-resolved
  local service integrations.
- Current confidence: partial; manifest-derived and checked against README,
  runbook, and current package manifests.

## Components

| Layer | Technology | Evidence | Notes |
| --- | --- | --- | --- |
| Language/runtime | Python >=3.10 | `pyproject.toml` | Active package runtime. |
| CLI | Python console script `mini-orchestrator` | `pyproject.toml`, `README.md` | Entry point `mini_orchestrator.cli:run_from_args`. |
| Web UI | Python stdlib HTTP server plus static HTML/JS | `mini_orchestrator/ui.py`, `mini_orchestrator/web/` | Active dashboard; startup must resolve config-service records. |
| Runtime storage | SQLite plus generated runtime/test-run folders | `mini_orchestrator/runtime_store.py`, `.mini_orchestrator/`, `tools/project-memory/runtime-sqlite-store.md` | Runtime DB is rebuild/runtime state, not source docs. |
| Dispatcher tools | Python scripts under `tools/codex-dispatcher/` | `tools/codex-dispatcher/README.md` | Runs dry-run, plan-only, and Codex app-server workflows. |
| Tests | pytest and stdlib unittest | `tests/`, `tools/codex-dispatcher/test_dispatcher.py` | Current full suite runs with `python -m pytest`. |
| Legacy/experimental app | TypeScript, React, Vite, Node/Express, Docker | `launch-desk/package.json`, `launch-desk/frontend/package.json`, `launch-desk/backend/package.json`, `launch-desk/*/Dockerfile` | Retained as legacy/experimental, not active Mini Orchestrator runtime. |
| GI/project memory | General Instructions kit | `tools/project-memory/instruction-kit.json`, `AGENTS.md` | GI is installed and updated through `tools/check-instruction-kit-updates.ps1`. |

## Commands

| Purpose | Command | Evidence |
| --- | --- | --- |
| Install | `python -m pip install -e .` | `README.md`, `tools/AGENT_RUNBOOK.md`, `pyproject.toml` |
| Run CLI | `python -m mini_orchestrator "<task>"` | `README.md`, `AGENTS.md` |
| Run UI | `python -m mini_orchestrator --ui` | `README.md`; requires config-service and Symphony availability checks |
| Test | `python -m pytest` | `tests/`, recent verification runs |
| Build | No active build pipeline | `README.md`, `tools/AGENT_RUNBOOK.md` |
| Legacy build | `npm run build:*` under `launch-desk/` | `launch-desk/package.json` |

## External Services

| Service | Role | Evidence | Boundary |
| --- | --- | --- | --- |
| GI config-service | Service discovery for local web/API runtimes | `README.md`, `AGENTS.md`, `tools/project-memory/service-runtime.json` | Resolve service records before binding ports or contacting neighboring services. |
| Symphony | External orchestration/reference daemon | `tools/project-memory/specs/integration-contracts/connected-projects.md` | Read-only external workspace unless explicitly authorized; task intake requires documented contract. |
| WorkNest | Task manager integration | `mini_orchestrator/worknest_bridge.py`, `tools/project-memory/task-manager.json` | Use config-service and documented manager contract only. |

## Gaps

- Confirm whether `launch-desk/` should stay in this repository long term or
  move to a separate archived/legacy boundary.
- Keep model defaults synchronized through the package configuration boundary
  rather than duplicating independent runtime defaults.
- Recheck config-service and Symphony command details before startup tasks; do
  not rely on stale ports from memory.
