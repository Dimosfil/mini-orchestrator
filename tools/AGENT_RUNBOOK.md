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

```powershell
python -m mini_orchestrator "search AGENTS"
```

## Build

```powershell
# No build pipeline exists yet.
```

## Smoke Check

```powershell
Test-Path .\AGENTS.md
Test-Path .\tools\agent-start.ps1
Test-Path .\mini-orchestrator-plan.md
```

Expected result:

```text
All commands return True.
```

## Logs

```powershell
# No runtime logs exist yet.
```

## Environment Notes

- Project is in bootstrap state.
- Current source material: `mini-orchestrator-plan.md`.
- Shared instruction kit source used for bootstrap:
  `D:\AI\general-instructions`.
