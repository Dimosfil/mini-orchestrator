# Handoff Summary: Generic Project Builder And Live Runs UX

Date: 2026-06-21 11:11:25
Thread topic: remove CRM hardcoding from active orchestrator runtime and make
Live Runs/Symphony observability clearer and less jittery.

## User Intent

- The dental CRM is only one generated project used to test the orchestrator.
- Mini Orchestrator must not hard-code CRM, dentistry, calculators, or any
  specific generated project domain into runtime behavior.
- The UI should clearly and sequentially show how an orchestrated task moves
  through Dispatcher/Symphony agents.
- Symphony daemon diagnostics should not look like user task cards.
- The dashboard should stop visually jumping on every polling refresh.

## Runtime Contract Decision

- Active runtime defaults are now domain-neutral.
- A missing/default visual agent card means `Project Builder`, not Dental CRM.
- Generated project artifacts should derive product domain, stack, slug, and
  version folder from the current user task.
- Generated outputs remain versioned under `.mini_orchestrator/test-runs/`
  unless the user explicitly names another target.
- Old CRM mentions in project memory are historical notes only, not current
  runtime contracts.

## Implemented

- Replaced active default visual-agent runtime constants in
  `mini_orchestrator/agent_profiles.py`:
  - `DEFAULT_DENTAL_CRM_*` removed.
  - `DEFAULT_PROJECT_BUILDER_CARD_ID = "project-builder"`.
  - `DEFAULT_PROJECT_BUILDER_TASK` now describes generic generated-project
    artifact work.
  - `default_project_builder_agent_card(...)` creates a neutral `Project
    Builder` card.
- Updated `mini_orchestrator/ui.py` so `/api/agents/default-card`,
  `/api/agents/compile`, and `/api/agents/run` use the neutral project builder
  default when no explicit card/task is provided.
- Updated focused tests to avoid domain-specific default assumptions:
  - `tests/test_agent_profiles.py`
  - `tests/test_visual_agent_task_run.py`
  - `tests/test_live_runs.py`
  - `tests/test_symphony_daemon.py`
- Updated Live Runs dashboard in `mini_orchestrator/web/index.html`:
  - added `Workflow log` panel showing the selected/active workflow stages,
    last events, status, source, and log path;
  - rendered Symphony daemon snapshots as compact health/observability cards
    instead of full task cards;
  - removed generated timestamp churn from the source subtitle;
  - skipped full Kanban/daemon DOM rerender when the live-runs payload has not
    materially changed;
  - added an in-flight guard so polling cannot overlap itself;
  - removed repeated card animation that made refreshes feel jumpy.
- Updated dashboard static tests in `tests/test_agent_builder_ui.py`.
- Updated `tools/project-memory/pending-tasks.md` with the completed
  `Symphony Workflow Visibility And Stable Refresh` checklist.

## Verification

- `rg -n "CRM|crm|Dental|dental|стомат|стоматолог|DEFAULT_DENTAL|default_dental|dental-crm-builder" mini_orchestrator tests`
  returned no matches.
- `python -m pytest tests/test_agent_profiles.py tests/test_visual_agent_task_run.py tests/test_live_runs.py tests/test_symphony_daemon.py tests/test_agent_builder_ui.py`
  passed: `52 passed`.
- `python -m compileall mini_orchestrator` passed.
- Dashboard script parse check passed earlier in the thread:
  `dashboard scripts parse: 1`.
- Local Mini Orchestrator UI was restarted:
  - previous process on port 8000 was `python -m mini_orchestrator --ui`;
  - new PID observed: `184064`;
  - `GET http://127.0.0.1:8000/health` returned `{"status":"ok"}`.
- `POST http://127.0.0.1:8000/api/agents/default-card` with `{}` returned:
  - `id = "project-builder"`;
  - `name = "Project Builder"`;
  - objective is generic generated-project artifact work.

## Current Dirty Files

- `mini_orchestrator/agent_profiles.py`
- `mini_orchestrator/ui.py`
- `mini_orchestrator/web/index.html`
- `tests/test_agent_builder_ui.py`
- `tests/test_agent_profiles.py`
- `tests/test_live_runs.py`
- `tests/test_symphony_daemon.py`
- `tests/test_visual_agent_task_run.py`
- `tools/project-memory/pending-tasks.md`

## Remaining UX Question

- The new `Workflow log` may still be too visually prominent for completed
  runs. The user questioned why it exists when it appeared as a large duplicate
  block. A good next pass is to make it collapsible or show it only for the
  selected/active run, while keeping the stage sequence available for debugging.

## Important Boundary

- Do not reintroduce CRM or dental as default orchestrator behavior.
- CRM may remain a test/generated artifact in `.mini_orchestrator/test-runs/`,
  but the orchestrator itself must stay generic and task-driven.
