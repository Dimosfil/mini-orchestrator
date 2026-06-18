# Handoff Summary: Visual-agent translation and mini-chat runtime

Date: 2026-06-18 12:20:27
Thread topic: Separate UI translation helper runtime from agent-card content and make mini-chat use persistent visual-agent Codex threads.

## User Decisions

- Work-package translation is application UI infrastructure, not content of the
  visual workflow agent card.
- Mini-chat is not a lightweight helper; it is a test of the real selected
  visual agent behavior.
- If mini-chat is slow, the runtime path needs to be fixed so agents work more
  like an already-open Codex chat.

## Implemented

- Translation helper runtime boundary:
  - `mini_orchestrator/agent_api.py`
  - `mini_orchestrator/web/agents-builder.html`
  - Translation now uses dedicated helper model `gpt-5.4-mini`.
  - UI no longer sends the selected card `llm` as the translation model.
  - Translation logs now show `model=translation-helper` on the frontend.
- Persistent visual-agent mini-chat path:
  - `mini_orchestrator/codex_dispatcher_service.py`
  - `mini_orchestrator/ui.py`
  - `mini_orchestrator/agent_api.py`
  - `tools/codex-dispatcher/codex_app.py`
  - Mini-chat can use a persistent per-card/profile Codex thread.
  - Card work-package fields are sent as thread `developerInstructions`.
  - User messages are sent as normal `turn/start` turns instead of being wrapped
    in a cold `orchestrator planner` dispatcher task.
  - Card reasoning is passed as Codex `effort`.
  - Added `/api/agents/chat-warmup` and frontend warmup when mini-chat opens.
- Updated tests:
  - `tests/test_agent_api.py`
  - Added coverage that mini-chat prefers the visual-agent runner when present.
  - Updated translation test so `gpt-5.5` from UI is ignored for translation and
    dispatcher receives `gpt-5.4-mini`.
- Updated project memory:
  - `tools/project-memory/agent-flow-builder.md`
  - `tools/project-memory/dispatcher-codex-optimization.md`
  - `tools/project-memory/pending-tasks.md`

## Measurements

- Previous mini-chat `привет` path:
  - About 13-14s.
  - Cause: fresh `gpt-5.5` Codex thread plus full planner worker wrapper.
  - Prompt included `Worker role: planner` and planner `high` reasoning config.
- New persistent visual-agent path:
  - Cold first send: 14.19s.
  - Second send in same thread: 2.35s.
  - Thread-only warmup: 5.28s, then first send 7.30s.
  - Warmup plus hidden priming turn: 5.25s + 9.13s, then real send 2.76s.
- Finding:
  - Persistent threads remove repeated `codex_thread_started`.
  - Remaining first-message latency is mostly Codex MCP/turn activation.
  - Fully fast first real send likely needs a hidden priming turn or a lower
    level way to pre-initialize Codex turn runtime without adding chat state.

## Runtime Status

- UI backend was started after changes.
- Health check passed:
  - `http://127.0.0.1:8000/health`
  - Response: `{"status":"ok"}`
- Listening process:
  - `127.0.0.1:8000`
  - PID observed: `1480`
- User should hard refresh:
  - `http://127.0.0.1:8000/agents-builder`

## Checks Run

- `python -m pytest tests\test_agent_api.py`
  - Result: 9 passed.
- `python -m compileall mini_orchestrator tools\codex-dispatcher`
  - Result: no errors.
- Live persistent visual-agent smoke through `PersistentCodexDispatcher`.
- UI health check through `Invoke-RestMethod`.

## Current Git Status

Modified:

- `mini_orchestrator/agent_api.py`
- `mini_orchestrator/ui.py`
- `mini_orchestrator/web/agents-builder.html`
- `tests/test_agent_api.py`
- `tools/codex-dispatcher/codex_app.py`
- `tools/codex-dispatcher/protocol.py`
- `tools/project-memory/agent-flow-builder.md`
- `tools/project-memory/pending-tasks.md`

Untracked:

- `mini_orchestrator/codex_dispatcher_service.py`
- `tools/project-memory/dispatcher-codex-optimization.md`
- `tools/summary/2026-06-17_20-08-44_CODEX_WORKER_TRANSLATION_LOGS_SUMMARY.md`
- `tools/summary/2026-06-18_12-20-27_VISUAL_AGENT_RUNTIME_SUMMARY.md`

## Next Step

In the browser, hard refresh `/agents-builder`, open mini-chat, wait briefly for
warmup, then send two simple messages. Inspect the newest dispatcher JSONL runs
to confirm:

- warmup creates or reuses a visual-agent thread;
- first send may still pay MCP/turn activation;
- second send should show `codex_thread_reused` and much lower latency.

Then decide whether to add a hidden priming turn during warmup. This improves
the next visible message but creates hidden conversation state and can make
immediate sends wait longer.
