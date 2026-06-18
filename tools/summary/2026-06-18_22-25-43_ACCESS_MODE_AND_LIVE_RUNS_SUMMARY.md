# Handoff Summary: Live Runs progress and visual-agent access mode

Date: 2026-06-18 22:25:43
Thread topic: Live workflow visibility, Codex file-change approval, and per-card access mode

## User Intent

- Make real mini-orchestrator workflows observable instead of timing out
  opaquely when Codex waits for file-change approval.
- Understand how Codex app-server maps to the Codex UI permission selector.
- Add an access selector to visual-agent cards, with full access as the
  temporary default so real file-writing workflow tests can continue.
- Create a summary and push the current scoped work.

## Implemented

- Live Runs now treats Codex file-change approval as a first-class state:
  - `mini_orchestrator/live_runs.py`
  - `tests/test_live_runs.py`
  - `mini_orchestrator/ui.py`
  - `mini_orchestrator/web/index.html`
  - `tools/codex-dispatcher/EVENT_PROTOCOL.md`
  - dispatcher run IDs are stable enough for UI polling.
- Visual-agent cards now have an access mode:
  - UI selector label: `Доступ`.
  - Values: `danger-full-access`, `workspace-write`, `read-only`.
  - Temporary default: `danger-full-access`.
  - Access mode is saved in flow snapshots, preset settings, mini-chat payloads,
    and response metadata.
- Codex app-server mapping was added:
  - `danger-full-access` maps to `approvalPolicy = "never"`, thread
    `sandbox = "danger-full-access"`, and turn
    `sandboxPolicy = {"type": "dangerFullAccess"}`.
  - `workspace-write` and `read-only` map to `approvalPolicy = "on-request"`
    and matching turn sandbox policies.
  - If no access mode is passed, old dispatcher behavior remains Codex-default.
- Persistent visual-agent profile hashing now includes `accessMode`, so changing
  access creates a new Codex thread with matching runtime settings.
- Project memory was updated:
  - `tools/project-memory/agent-flow-builder.md`
  - `tools/project-memory/pending-tasks.md`
  - `tools/project-memory/specs/agent-worker-profile-snapshot.example.json`
  - connected-project and preference notes already present in the working tree
    were preserved.

## Verification

- `python -m pytest`
  - Result: 34 passed.
- `python -m compileall mini_orchestrator tools\codex-dispatcher`
  - Result: no errors.
- Inline script parse check for `mini_orchestrator/web/agents-builder.html`
  through Node:
  - Result: `inline scripts parse ok: 1`.
- UI health:
  - `http://127.0.0.1:8000/health` returned `{"status":"ok"}`.
- HTTP live smoke after restarting the UI on port 8000:
  - `/api/agents/chat` returned `OK_ACCESS_HTTP_CURRENT_CODE`.
  - Response included `accessMode = "danger-full-access"`.
  - Dispatcher log confirmed `approvalPolicy = "never"` and
    `sandboxPolicy = {"type": "dangerFullAccess"}`.
- Attempting to start a second UI on port 8001 was blocked by config-service
  because this app is registered for port 8000, confirming startup port
  enforcement still works.

## Current Runtime Status

- UI is running at `http://127.0.0.1:8000/`.
- The active UI process was restarted after code changes so HTTP smoke used the
  current access-mode implementation.
- Only port 8000 is listening for this app; the failed 8001 attempt did not
  leave a listener.

## Risks / Next Steps

- `danger-full-access` intentionally removes sandbox boundaries. It is currently
  a temporary default for local workflow testing and should remain visible in
  the card UI.
- Live Runs can now show `waiting_approval`, but a full approval bridge
  (approve/decline from mini-orchestrator UI) is still a separate future task.
- Serious workflow execution should eventually use an explicit run lifecycle and
  per-task workspace policy rather than relying only on visual-agent mini-chat
  threads.
