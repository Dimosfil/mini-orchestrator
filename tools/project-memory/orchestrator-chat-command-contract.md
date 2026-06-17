# Orchestrator Chat Command Contract

Date: 2026-06-16

## Purpose

Provide a temporary chat-first entry point for the Codex-native dispatcher while
the full mini-orchestrator UI/API flow is still evolving. A user can send a
short chat command and the agent can route it through the dispatcher chain.

## Command Forms

- `оркестратор <task>` or `orchestrator <task>`: pass `<task>` through the
  dispatcher chain.
- `оркестратор план <task>` or `orchestrator plan <task>`: normalize as a
  planner-directed task, then run planner -> executor -> reviewer.
- `оркестратор исполнитель <task>` or `orchestrator executor <task>`: normalize
  as an executor-directed task, then run planner -> executor -> reviewer.
- `оркестратор ревью <task>` or `orchestrator review <task>`: normalize as a
  reviewer-directed task, then run planner -> executor -> reviewer.

## Initial Safety Rule

For early tests from this chat, run the dispatcher in dry-run mode unless the
user explicitly asks to launch a real Codex worker. Use `--chain --dry-run` for
chat commands. Dry-run still verifies the command parser, normalized
`next_input`, chain role order, and event log contract.

## Local Test Project Mode

When the user sends a chat-gated plan command, first return the planner proposal
without creating files:

```powershell
python tools\codex-dispatcher\dispatcher.py --task "<original command>" --plan-only
```

`--plan-only` must not create files and must not be limited to supported local
demo projects. Without `--dry-run`, it sends the request to the planner worker
through Codex app-server and returns that task-specific planner proposal. With
`--dry-run`, it may return a local fallback approval plan for parser and log
contract smoke tests.

Wait for explicit user approval in chat. After approval, use dispatcher local
test project mode before launching a broad Codex worker:

```powershell
python tools\codex-dispatcher\dispatcher.py --task "<original command>" --local-test-project
```

This mode currently supports `calculator` and `construction-crm` demo tasks. It
creates or refreshes a managed project under `test-projects/<demo-project>`,
writes code and tests, then runs bounded executor -> test/review iterations. If
test/review fails, the next executor iteration receives the review output and
tries again until checks pass or the iteration limit is reached. After a clean
review, it launches/smokes the application, runs any declared UI smoke checks,
and returns planner, executor, and reviewer outputs with
`localTestProject=true`. UI demo projects must not pass with inert static
buttons: the reviewer output must include `UI smoke`, and that check must fail
when declared buttons have no interaction contract or handler script. The mode
must refuse to overwrite an existing non-managed project directory.

## Implementation Map

- Parser and routing: `tools/codex-dispatcher/dispatcher.py`
- Tests: `tools/codex-dispatcher/test_dispatcher.py`
- User-facing dispatcher docs: `tools/codex-dispatcher/README.md`
- Agent-facing command rules: `AGENTS.md`, `tools/AGENT_WORKING_AGREEMENTS.md`
- Generated local demo projects: `test-projects/`

## Verification

- Unit tests must cover planner-forced chat commands and default Russian task
  routing such as `оркестратор Сделай мне калькулятор`.
- Unit tests must cover plan-only chat approval mode.
- Local test project verification must show an executor -> test/review pass, a
  launch/smoke result, and `UI smoke` for demo projects that include browser UI.
- A dry-run smoke command must show only the selected worker in `agents`.
