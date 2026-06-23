# Orchestrator Chat Command Contract

Date: 2026-06-16

## Purpose

Provide a temporary chat-first entry point for the Codex-native dispatcher while
the full mini-orchestrator UI/API flow is still evolving. A user can send a
short chat command and the agent can route it through the dispatcher chain.

Project goal reminder: Mini Orchestrator is the product. Generated applications
such as calculator, CRM, or dental CRM are workload artifacts used to test and
demonstrate orchestration behavior; they are not the product goal and must not
be treated as the project identity.

## Command Forms

- `оркестратор <task>` or `orchestrator <task>`: pass `<task>` through the
  dispatcher chain.
- `оркестратор план <task>` or `orchestrator plan <task>`: normalize as a
  planner-directed task, then run planner -> executor -> reviewer.
- `оркестратор исполнитель <task>` or `orchestrator executor <task>`: normalize
  as an executor-directed task, then run planner -> executor -> reviewer.
- `оркестратор ревью <task>` or `orchestrator review <task>`: normalize as a
  reviewer-directed task, then run planner -> executor -> reviewer.

## Execution Rule

Chat `orchestrator` / `оркестратор` requests are real orchestration requests by
default. Do not use `--dry-run` for chat, smoke, release, or `gi test`
verification. When the web UI or dashboard has a selected execution mode and
chain preset, the chat command must honor that product workflow instead of
starting an unrelated low-level dispatcher run.

If the selected mode is Symphony, submit through Mini Orchestrator's
`POST /api/symphony/runs` with `approved=true` and the saved selected chain
preset. If the selected mode is Dispatcher, submit through the approved
dispatcher workflow endpoint or release dispatcher chain with the saved chain
preset. Do not bypass the UI/API workflow with a standalone CLI command when
that would ignore selected mode, preset settings, or Kanban state.

## Chat-Gated Release Chain

When the user sends a chat-gated plan command, first return the planner proposal
without creating files:

```powershell
python tools\codex-dispatcher\dispatcher.py --task "<original command>" --plan-only
```

`--plan-only` must not create files and must not be limited to supported local
demo projects. It sends the request to the planner worker through Codex
app-server and returns that task-specific planner proposal.

Wait for explicit user approval in chat. After approval, use the release
dispatcher chain:

```powershell
python tools\codex-dispatcher\dispatcher.py --task "<original command>" --chain
```

The release dispatcher no longer supports local calculator/CRM demo generation
or `--local-test-project`. Approved work is routed through the selected
orchestrator workflow and selected chain preset. Dry-run output is not valid
release, chat, or system verification evidence.

## Implementation Map

- Parser and routing: `tools/codex-dispatcher/routing.py`
- Pipeline: `tools/codex-dispatcher/pipeline.py`
- Codex app-server transport: `tools/codex-dispatcher/codex_app.py`
- CLI entrypoint: `tools/codex-dispatcher/cli.py`
- Tests: `tools/codex-dispatcher/test_dispatcher.py`
- User-facing dispatcher docs: `tools/codex-dispatcher/README.md`
- Agent-facing command rules: `AGENTS.md`, `tools/AGENT_WORKING_AGREEMENTS.md`

## Verification

- Unit tests must cover planner-forced chat commands and default Russian task
  routing such as `оркестратор Сделай мне калькулятор`.
- Unit tests must cover plan-only chat approval mode.
- Release chain tests must show planner -> executor -> reviewer handoff order
  through an injectable Codex transport.
- Release, chat, and `gi test` verification must use real dispatcher or
  Mini-owned Symphony execution. Legacy dry-run transport is internal-only and
  guarded by `MINI_ORCHESTRATOR_ENABLE_LEGACY_DRY_RUN=1`.
