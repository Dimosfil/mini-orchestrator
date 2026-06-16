# Handoff Summary: Codex app-server dispatcher smoke and routing fix

Date: 2026-06-16 18:03:26

## Goal

Continue the Codex-native dispatcher task from the prior sprint summary:
run a real `codex app-server` smoke test, fix blockers, and confirm the
dispatcher can drive Codex agents through the app-server protocol.

## Implemented

- Installed/validated Codex CLI through npm outside this repo:
  - `codex-cli 0.140.0`
  - `codex app-server --help` works.
  - `codex doctor` reports healthy install, auth, websocket, and config.
- Updated dispatcher Windows command resolution:
  - prefers `codex.cmd` on Windows instead of the blocked WindowsApps
    `codex.exe` path.
  - supports `CODEX_COMMAND` and `--codex-command` overrides.
- Hardened app-server process handling in
  `tools/codex-dispatcher/dispatcher.py`:
  - async stdout reader with internal request/turn timeouts.
  - async stderr drain to avoid blocking when Codex emits plugin/skill warnings.
  - graceful terminate/kill on context exit.
- Aligned dispatcher app-server JSON-RPC payloads with the working
  `codex debug app-server send-message-v2` shape:
  - initialize capabilities include `requestAttestation=false` and opt-out
    notification methods.
  - `thread/start` and `turn/start` include the current protocol's nullable
    fields.
  - final answer collection reads `item/completed` agent messages, not only
    `item/agentMessage/delta`.
- Added dispatcher selection layer through the real Codex agent run:
  - `DispatchDecision(role, reason, confidence, next_input)`.
  - conservative routing currently selects one worker.
  - planner-directed and ambiguous requests route to `planner`.
  - CLI output now includes `dispatchDecision`.
- Updated dispatcher docs/tests:
  - `tools/codex-dispatcher/protocol.py`
  - `tools/codex-dispatcher/EVENT_PROTOCOL.md`
  - `tools/codex-dispatcher/README.md`
  - `tools/codex-dispatcher/test_dispatcher.py`
  - `tools/project-memory/pending-tasks.md`

## Checks Run

```powershell
codex app-server --help
codex doctor
codex exec --ephemeral "Say only: exec smoke ok"
codex debug app-server send-message-v2 "Say only: app-server debug smoke ok"
python -m py_compile tools\codex-dispatcher\dispatcher.py
python -m py_compile tools\codex-dispatcher\dispatcher.py tools\codex-dispatcher\protocol.py tools\codex-dispatcher\worknest.py
python -m unittest discover -s tools\codex-dispatcher -p "test_*.py"
python tools\codex-dispatcher\dispatcher.py --task "Say only: dispatcher smoke ok" --turn-timeout-seconds 90 --request-timeout-seconds 30
python tools\codex-dispatcher\dispatcher.py --task "Plan the next smallest improvement to the dispatcher" --turn-timeout-seconds 120 --request-timeout-seconds 30
python tools\codex-dispatcher\dispatcher.py --task "Plan a small dispatcher improvement" --dry-run
```

## Verified Status

- Real `codex app-server` path works from dispatcher.
- Three-agent smoke completed after stderr drain fix:
  - planner: `dispatcher smoke ok`
  - executor: `dispatcher smoke ok`
  - reviewer: `dispatcher smoke ok`
- Real task run completed:
  - planner proposed smallest improvement.
  - executor implemented one-worker dispatch decision layer.
  - reviewer found only stale CLI help text.
  - stale CLI help text was fixed afterward.
- Focused tests pass:
  - `Ran 2 tests ... OK`.
- Syntax checks pass.
- Dry-run CLI now prints `dispatchDecision` and only the selected worker.

## Important Notes

- The earlier hang was caused by `stderr=PIPE` without a reader. Codex emitted
  enough warnings that app-server could block before model output.
- Do not reintroduce blocking direct reads from app-server stdout/stderr.
- On Windows, avoid resolving `codex` to the WindowsApps `codex.exe` shim for
  subprocess use. The npm `codex.cmd` shim is the working command.
- The current routing layer is intentionally narrow. It does not yet contain
  executor/reviewer selection heuristics.

## Separate Known Issue

- Codex Desktop displayed a crash/error related to plugin manifest validation:
  `ngs-analysis` has `interface.defaultPrompt[0]` longer than 128 characters.
- CLI/app-server can still run, but the plugin manifest should be fixed or the
  plugin disabled if Desktop keeps crashing.
- The affected path shown by Codex was under:
  `C:\Users\Fil-Dom\.codex\.tmp\plugins\plugins\ngs-analysis\.codex-plugin\plugin.json`.

## Suggested Next Step

Implement the next narrow routing increment:

- define explicit executor/reviewer route conditions;
- keep ambiguous tasks falling back to planner;
- add focused tests for each new role route;
- avoid broad queue, retry, or persistence work until the role contract is
  stable.
