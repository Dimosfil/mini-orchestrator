# Handoff Summary: mini-orchestrator UI and LLM coordinator layer

Date: 2026-06-16 14:39:39
Thread topic: Web UI startup, GI config-service URL, and first LLM-backed coordinator layer

## Goal

- Make the mini-orchestrator visible through a local web UI.
- Configure GI config-service URL as requested.
- Add the first real LLM-backed orchestrator layer so natural language can be
  planned through a coordinator model instead of only rule parsing.

## Implemented

- Added Web UI mode:
  - `mini_orchestrator/ui.py`
  - `mini_orchestrator/web/index.html`
  - CLI flags: `--ui`, `--host`, `--port`, `--open-browser`.
- Configured shared GI config-service URL:
  - `D:/AI/general-instructions/config/gi-main.json`
  - `configServiceUrl` is `http://127.0.0.1:4100`.
- Added first LLM coordinator layer:
  - `mini_orchestrator/llm.py` implements an OpenAI Responses API client using
    stdlib HTTP.
  - `mini_orchestrator/planner.py` now tries an LLM planner when enabled and
    falls back to rule-based planning when no API key is available.
  - LLM planner returns only allowlisted tool actions.
- Added `respond` as a safe local tool:
  - Natural-language or unsupported requests can now finish with
    `status=done`, `tool=respond`, instead of `needs_routing_check`.
- Updated config and CLI:
  - `MINI_ORCHESTRATOR_LLM_PROVIDER`
  - `MINI_ORCHESTRATOR_COORDINATOR_MODEL`
  - `MINI_ORCHESTRATOR_EXECUTOR_MODEL`
  - `MINI_ORCHESTRATOR_OPENAI_BASE_URL`
  - `--llm-provider auto|openai|rules|off`
  - `--coordinator-model`
  - `--executor-model`
  - `--openai-base-url`.
- Updated README with LLM coordinator setup and fallback behavior.
- Updated `tools/project-memory/pending-tasks.md` with completed LLM coordinator
  checklist.

## Current Runtime Status

- UI is running at `http://127.0.0.1:8000/`.
- Health check passed at `http://127.0.0.1:8000/health`.
- Config-service is available at `http://127.0.0.1:4100/services`.
- Current environment did not expose `OPENAI_API_KEY`, so live LLM calls were
  not verified.

## Checks Run

- `python -m mini_orchestrator --help`
- `python -m compileall mini_orchestrator`
- `python -m mini_orchestrator "search AGENTS" --no-log`
- `python -m mini_orchestrator "<cat image request>" --no-log`
- `python -m mini_orchestrator "hello" --llm-provider openai --no-log`
- `Invoke-RestMethod http://127.0.0.1:8000/health`
- `Invoke-RestMethod http://127.0.0.1:8000/api/run`
- `Invoke-RestMethod http://127.0.0.1:4100/services`

## Notable Behavior

- Without `OPENAI_API_KEY`, `--llm-provider auto` uses the rule-based fallback.
- With `--llm-provider openai` and no key, the orchestrator returns a clear
  direct response: `OPENAI_API_KEY is not set`.
- A cat-image request no longer stalls in `needs_routing_check`;
  it returns a direct response saying the current tool layer cannot generate
  images yet.

## Risks / Next Steps

- Real OpenAI LLM execution still needs an `OPENAI_API_KEY` in the environment.
- Image generation, web browsing, and multi-agent delegation are not implemented
  as mini-orchestrator tools yet.
- UI is still diagnostic-first; it now shows `tool_output`, but the full JSON
  remains visible for debugging.
- The workspace appears fully untracked in git status; do not assume unrelated
  files are safe to delete or reset.
