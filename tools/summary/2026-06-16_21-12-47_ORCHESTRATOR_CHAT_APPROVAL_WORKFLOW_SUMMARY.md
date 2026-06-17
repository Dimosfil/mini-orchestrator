# Handoff Summary: Orchestrator Chat Approval Workflow

Date: 2026-06-16 21:12:47
Thread topic: Add chat-gated orchestrator plan approval, local calculator demo workflow, and run the approved workflow.

## User Intent

- User expected `оркестратор план Сделай калькулятор` to first show a plan in chat.
- User then confirms the plan in chat.
- Only after confirmation should the system create a test project, write code,
  run executor -> test/review loops, fix until clean, then final review and
  launch/smoke the application.

## Implemented

- Added dispatcher `--plan-only` mode:
  - Returns only planner output.
  - Does not create project files.
  - Produces Russian plan text for Russian tasks.
- Added dispatcher `--local-test-project` approved workflow:
  - Creates managed demo projects only under `test-projects/`.
  - Currently supports calculator tasks.
  - Refuses to overwrite existing non-managed project directories.
  - Runs bounded executor -> test/review iterations.
  - If checks fail, the next executor iteration receives the previous review.
  - After clean review, runs an application launch/smoke command.
- Added generated calculator template:
  - `calculator.py`
  - `test_calculator.py`
  - `README.md`
- Added tests for:
  - Plan-only approval mode.
  - Real local calculator project workflow in a temporary test directory.
- Updated docs/contracts:
  - `AGENTS.md`
  - `tools/codex-dispatcher/README.md`
  - `tools/codex-dispatcher/EVENT_PROTOCOL.md`
  - `tools/project-memory/orchestrator-chat-command-contract.md`
  - `tools/project-memory/pending-tasks.md`
- Added `test-projects/` to `.gitignore`.

## Commands Run

- Removed old generated `test-projects/calculator` after verifying
  `.mini-orchestrator-demo.json`.
- `python test_dispatcher.py` from `tools/codex-dispatcher`:
  - 10 tests passed.
- `python -m compileall tools\codex-dispatcher`:
  - Passed.
- `python tools\codex-dispatcher\dispatcher.py --task "оркестратор план Сделай калькулятор" --plan-only`:
  - Returned Russian approval plan and did not create `test-projects/calculator`.
- After user said `запускай`:
  - `python tools\codex-dispatcher\dispatcher.py --task "оркестратор план Сделай калькулятор" --local-test-project`
  - Created `test-projects/calculator`.
  - Unit tests passed: 5 tests OK.
  - Launch smoke passed: `add 2 3` returned `5`.

## Current Generated Demo Project

- `test-projects/calculator/` exists.
- Files:
  - `.mini-orchestrator-demo.json`
  - `calculator.py`
  - `test_calculator.py`
  - `README.md`
  - `__pycache__/`
- The directory is ignored by git through `test-projects/`.

## UI Observation

- User asked to start UI.
- `http://127.0.0.1:8000/health` returned `ok`, so the UI was already running.
- Browser opened `http://127.0.0.1:8000/`.
- Screenshot showed `Campaign Concept Studio`.
- Verified that `mini_orchestrator/web/index.html` currently contains that UI,
  so the current mini-orchestrator web UI is not an orchestrator/calculator UI.

## Important Current Git State

`git status --short` showed:

```text
 M .gitignore
 M AGENTS.md
 M tools/AGENT_WORKING_AGREEMENTS.md
 M tools/codex-dispatcher/EVENT_PROTOCOL.md
 M tools/codex-dispatcher/README.md
 M tools/codex-dispatcher/dispatcher.py
 M tools/codex-dispatcher/test_dispatcher.py
 M tools/project-memory/pending-tasks.md
?? COMMANDS.md
?? tools/project-memory/orchestrator-chat-command-contract.md
```

Some modified/untracked files predated the latest changes. Do not revert or
commit unrelated work without inspecting scope.

## Likely Next Steps

- If the user wants to test from PowerShell, use:

```powershell
python tools\codex-dispatcher\dispatcher.py --task "оркестратор план Сделай калькулятор" --plan-only
python tools\codex-dispatcher\dispatcher.py --task "оркестратор план Сделай калькулятор" --local-test-project
```

- If the user asks about the browser UI, likely next task is replacing
  `Campaign Concept Studio` with an actual mini-orchestrator UI, or creating a
  web UI for the generated calculator.
