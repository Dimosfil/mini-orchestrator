# Codex Dispatcher Prototype

This prototype is the Codex-native orchestration path for the mini-orchestrator.
It coordinates multiple Codex threads through `codex app-server` instead of
calling OpenAI models directly.

## Flow

Single-worker mode:

1. Start Codex app-server as a subprocess.
2. Classify the user task into one worker role with a `DispatchDecision`.
3. Create one thread for the selected worker.
4. Send the selected worker the decision's `next_input`.
5. Return a dispatcher summary and write a JSONL event log.

Chain mode:

1. Classify and normalize the user task into a `DispatchDecision`.
2. Load workers from `--chain-preset-id` when the dashboard selected a chain.
3. Run the workers in the selected chain graph order, passing prior worker
   outputs forward.
4. If no chain preset id is supplied, run the configured default
   `planner -> executor -> reviewer` chain.
5. Return all role outputs and write a JSONL event log with `chain=true`.

The decision includes `role`, `reason`, `confidence`, and `next_input`.
Planner-directed tasks route to `planner`; explicit implementation/editing
tasks route to `executor`; explicit review/verification tasks route to
`reviewer`. Ambiguous tasks still fall back to `planner`.

## Worker Profiles

Default worker models are configuration-backed:

- `planner`: `MINI_ORCHESTRATOR_COORDINATOR_MODEL`, default `gpt-5.5`
- `executor`: `MINI_ORCHESTRATOR_EXECUTOR_MODEL`, default `gpt-5.3-codex-spark`
- `reviewer`: `MINI_ORCHESTRATOR_REVIEWER_MODEL`, default follows the
  coordinator model

When `--chain-preset-id` is provided, worker names, models, reasoning levels,
access modes, order, and instructions are derived from the selected agent chain
preset stored in `.mini_orchestrator/runtime.sqlite3`. Generated profile
instructions stay in memory on the worker object instead of being written under
`.mini_orchestrator/dispatcher-chain-profiles/`. Every executable agent in that
preset must include its own `llm`; missing models are rejected instead of being
filled from role defaults. `--chain-preset-file` remains available for manual
compatibility runs outside the dashboard path.
Real Codex app-server runs pass the selected worker model by default. Use
`--model <name>` to override all worker model labels for a run, or
`--use-codex-default-models` to let the current Codex config choose the model.
Dispatcher CLI agent turns wait up to 300 seconds by default. Override with
`--turn-timeout-seconds <seconds>` or
`MINI_ORCHESTRATOR_DISPATCHER_TURN_TIMEOUT_SECONDS` for heavier release-chain
runs.

## Generated App Artifacts

Release-chain tests that ask workers to generate a runnable app, CRM, demo, or
prototype must create a separate project-named version folder under
`.mini_orchestrator/test-runs/<task-slug>/<version>/`.

Workers must not modify `launch-desk/` or another existing app only because it
looks like a convenient web project. Use an existing folder only when the user
explicitly names it as the target. Every repeat run should leave the previous
artifact inspectable, with a README or manifest describing the original task,
entry point, run date, and verification notes.

## Usage

Real Codex app-server run:

```powershell
python tools\codex-dispatcher\dispatcher.py --task "Implement the next scoped task"
```

Real full chain run:

```powershell
python tools\codex-dispatcher\dispatcher.py --task "оркестратор план Сделай калькулятор" --chain
```

Real full chain run with a dashboard-selected preset:

```powershell
python tools\codex-dispatcher\dispatcher.py --task "Approved workflow task" --chain --chain-preset-id ui-abc123
```

Chat approval plan, no file writes:

```powershell
python tools\codex-dispatcher\dispatcher.py --task "orchestrator plan Make a calculator" --plan-only
```

By default this starts only the planner worker through Codex app-server and
returns its task-specific proposal.

Approved release chain after the user accepts a plan:

```powershell
python tools\codex-dispatcher\dispatcher.py --task "orchestrator plan Make a calculator" --chain
```

The release dispatcher no longer includes local calculator/CRM demo project
generation, `--local-test-project`, or dry-run verification.

Supported chat command forms:

- `оркестратор <task>` / `orchestrator <task>`: route the task normally.
- `оркестратор план <task>` / `orchestrator plan <task>`: normalize as
  planner-directed.
- `оркестратор исполнитель <task>` / `orchestrator executor <task>`: force
  executor in single-worker mode, or start from executor-directed input in chain
  mode.
- `оркестратор ревью <task>` / `orchestrator review <task>`: force reviewer in
  single-worker mode, or start from reviewer-directed input in chain mode.

Claim the next WorkNest task and route it through the dispatcher:

```powershell
$env:GI_CONFIG_SERVICE_URL = "http://127.0.0.1:4100"
python tools\codex-dispatcher\dispatcher.py --from-worknest --project mini-orchestrator
```

Generated runtime logs are written under `tools/codex-dispatcher/runs/` and are
ignored by git.

See `EVENT_PROTOCOL.md` for the JSONL event contract.
