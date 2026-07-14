<p align="center">
  <img src="images/mini-orchestrator-banner.png" alt="Mini Orchestrator — AI-agent workflow lab" width="100%">
</p>

# Mini Orchestrator: detailed guide

**English** · [Русский](README.extended.ru.md) · [Short README](../README.md)

## Purpose

Mini Orchestrator is a lightweight workspace for experiments with configurable
AI-agent workflows. Its central contract is simple: planning is visible,
execution requires explicit approval, handoffs are inspectable, and results do
not become final until a human accepts them.

The project owns task cards, workflow configuration, approvals, routing,
persistence, limits, and Human Review. Dispatcher and Symphony are execution
adapters around that project-owned lifecycle.

## Main workflow

1. Enter a task, for example `orchestrator plan Build a calculator`.
2. Request a plan preview. The real planner worker returns a structured proposal.
3. Inspect the proposal and technical metadata.
4. Explicitly confirm the plan.
5. Select a saved agent-chain preset and start the workflow.
6. Follow stages and results in Live Runs.
7. Accept the result in Human Review or send it back for another pass.

The default `planner -> executor -> reviewer` preset demonstrates the workflow.
It is not hard-coded: validated presets may use a different number, order, role,
model, reasoning level, access mode, and work package for their agents.

## Product areas

### Dashboard and Live Runs

The main dashboard owns approved execution. It displays one task card throughout
the run and exposes stage status, recent events, output summaries, selected
chain, and reviewer verdict. Live Runs can show Dispatcher, Symphony, or a
combined view.

### Agent Builder

The visual builder creates agent cards and graph connections. Draft/import state
may remain in browser `localStorage`; named flows and chain presets are persisted
by the backend. A user can review an approval manifest containing the task,
agent order, models, reasoning and access settings, workspace policy, and first
prompt summary.

Compiling a manifest validates and freezes configuration. It does not start
workers. Execution still begins from the approved dashboard flow.

### Human Review

Successful or `needs_changes` results enter Human Review. The user explicitly
accepts the result into Done or requests rework. WorkNest terminal completion is
reported only after that acceptance.

### Evaluation suites

The backend can persist and run software-artifact evaluation suites. This is a
verification surface for workflow outputs, separate from approval and task
lifecycle ownership.

## Execution modes

### Dispatcher

Dispatcher executes the selected preset through Codex app-server workers. Plan
preview and approved execution are separate operations:

```powershell
python tools\codex-dispatcher\dispatcher.py --task "<task>" --plan-only
python tools\codex-dispatcher\dispatcher.py --task "<task>" --chain
```

For a real project `gi test`, use the project runner so saved dashboard settings
are preserved:

```powershell
python tools\run_gi_test.py --task "<release or full-system test task>"
```

### Symphony

Symphony intake is contract-gated. In the production business flow, Mini
Orchestrator keeps ownership of the task card, checklist, chain order, and
persistence. It sends one agent handoff at a time, waits for the retained
Symphony result, and then passes previous structured outputs to the next agent.

If the configured Symphony record does not expose a documented intake endpoint,
Mini Orchestrator records a visible blocked run instead of claiming that the
task was accepted.

### Package-native core

The package also contains a smaller `plan -> execute -> validate` loop:

```powershell
python -m mini_orchestrator "search AGENTS"
```

Its LLM coordinator is optional and can fall back to rules. This path is useful
for core experiments but is separate from the dashboard's preset workflow.

## Runtime and persistence

Project-owned runtime state is stored in:

```text
.mini_orchestrator/runtime.sqlite3
```

SQLite stores saved flows, immutable manifests, dispatcher tasks, process
output, agent cards, chain presets, worker profiles, evaluation data, and
Symphony gateway state. Generated runnable test artifacts remain file-based
under `.mini_orchestrator/test-runs/`.

The canonical compiled-manifest runtime follows explicit success/failure edges,
emits structured stage artifacts, bounds retry and rework loops, limits context,
and checkpoints transitions for resume after interruption.

Legacy runtime files can be imported with:

```powershell
python tools\migrate_runtime_to_sqlite.py
```

Use `--prune-files` only after a successful import and verification.

## Service dependencies

UI startup follows GI config-service rules. Mini Orchestrator resolves its own
service record with:

```text
GET /services/mini-orchestrator
```

The record must provide `baseUrl`, `endpoints.availability`, and `endpoints.api`.
Startup stops instead of guessing a fallback host or port when required service
configuration is unavailable.

The project-local runtime selector is:

```text
tools/project-memory/service-runtime.json
```

The full dashboard also requires the configured Symphony service to be
available. An unavailable Symphony service makes combined operational startup
incomplete, even though Dispatcher data remains visible in the combined view.

WorkNest is the external task source and terminal completion sink. Its bridge is
limited to documented claim and terminal-completion operations resolved through
config-service.

## Install and run

Requirements: Python 3.10+, project dependencies, and valid GI service records.

```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1
python -m pip install -e .
python -m mini_orchestrator --ui
```

Optional UI flags:

- `--host`: expected host; it must match config-service;
- `--port`: expected port; it must match config-service;
- `--open-browser`: open the UI after startup.

## Configuration

Important environment variables:

- `OPENAI_API_KEY`;
- `MINI_ORCHESTRATOR_LLM_PROVIDER` (`auto`, `openai`, `rules`, or `off`);
- `MINI_ORCHESTRATOR_COORDINATOR_MODEL`;
- `MINI_ORCHESTRATOR_EXECUTOR_MODEL`;
- `MINI_ORCHESTRATOR_OPENAI_BASE_URL`;
- `MINI_ORCHESTRATOR_DAEMON_STATE_URL`;
- `MINI_ORCHESTRATOR_SYMPHONY_SERVICE_ID`;
- `MINI_ORCHESTRATOR_DISPATCHER_STALE_AFTER_SECONDS`.

Never commit real secrets. Local environment files remain local.

## API overview

| Area | Main endpoints |
|---|---|
| Health and service contract | `GET /health`, `GET /agent/guide`, `GET /agent/contract` |
| Core workflow | `POST /api/run` |
| Dispatcher | `POST /api/dispatcher/plan`, `POST /api/dispatcher/run` |
| Agent cards | `POST /api/agents/chat`, `GET /api/agents/default-card`, `POST /api/agents/compile`, `POST /api/agents/run` |
| Saved flows | `GET/POST /api/agent-flows`, `GET/PUT /api/agent-flows/{id}`, `POST /api/agent-flows/{id}/validate`, `POST /api/agent-flows/{id}/compile` |
| Chain presets | `GET /api/agent-chain-presets`, `PUT/DELETE /api/agent-chain-presets/{id}` |
| Evaluations | `GET/POST /api/evals/suites`, `POST /api/evals/run`, `GET /api/evals/runs` |
| Live state | `GET /api/daemon/runs?source=combined|dispatcher|symphony` |
| Symphony | `POST /api/symphony/runs`, `POST /api/symphony/refresh`, `GET /api/symphony/issues/{issueIdentifier}` |
| WorkNest | `POST /api/worknest/claim`, `POST /api/worknest/complete` |

The strict machine-readable contract at `GET /agent/contract` is authoritative
for integrations.

## Observability and failure behavior

The technical view exposes runtime and log paths, dispatch decisions, worker
thread/turn identifiers, timings, event counts, and compact recent events. Full
prompts and outputs stay in the referenced logs.

Old incomplete Dispatcher runs become `stale` after the configured timeout when
their process is gone or their log no longer changes. They leave the active
count and appear in Human Review with a reason. Symphony integration failures
remain visible as blocked gateway runs.

## Current boundaries

- The project is an experimental lab and is still evolving.
- The dashboard is the active product surface.
- `launch-desk/` is retained as a legacy/experimental application and is not
  part of the active runtime.
- The visual builder constructs and validates workflows; it does not bypass
  approval or launch workers by itself.
- Mini Orchestrator remains the lifecycle owner even when an external execution
  adapter runs agent work.

## Verification

```powershell
python -m compileall mini_orchestrator tools\codex-dispatcher
python -m pytest tests
python tools\run_gi_test.py --task "orchestrator plan Smoke test"
python -m mini_orchestrator "search AGENTS" --no-log
```
