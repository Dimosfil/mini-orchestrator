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
2. Run `planner` with the normalized `next_input`.
3. Pass planner output to `executor`.
4. Pass planner and executor output to `reviewer`.
5. Return all role outputs and write a JSONL event log with `chain=true`.

Local test project mode:

1. Classify and normalize the user task into a `DispatchDecision`.
2. Run the fixed planner -> executor -> reviewer chain locally after approval.
3. Create a supported demo project under `test-projects/`.
4. Run executor -> test/review iterations until checks pass or the limit is
   reached.
5. After a clean review, launch/smoke the application, run any declared UI
   smoke checks, and return role outputs with `localTestProject=true`.

The decision includes `role`, `reason`, `confidence`, and `next_input`.
Planner-directed tasks route to `planner`; explicit implementation/editing
tasks route to `executor`; explicit review/verification tasks route to
`reviewer`. Ambiguous tasks still fall back to `planner`.

## Roles

- `planner`: `gpt-5.5`, high reasoning
- `executor`: `gpt-5.4`, medium reasoning
- `reviewer`: `gpt-5.4-mini`, high reasoning

The role instructions are sourced from `.codex/agents/*.toml`.

## Usage

Dry run, no Codex process:

```powershell
python tools\codex-dispatcher\dispatcher.py --task "Plan a small refactor" --dry-run
```

Full chain dry run, no Codex process:

```powershell
python tools\codex-dispatcher\dispatcher.py --task "оркестратор план Сделай калькулятор" --chain --dry-run
```

Real Codex app-server run:

```powershell
python tools\codex-dispatcher\dispatcher.py --task "Implement the next scoped task"
```

Real full chain run:

```powershell
python tools\codex-dispatcher\dispatcher.py --task "оркестратор план Сделай калькулятор" --chain
```

Chat-style command dry run:

```powershell
python tools\codex-dispatcher\dispatcher.py --task "оркестратор план Сделай калькулятор" --dry-run
```

Chat approval plan, no file writes:

```powershell
python tools\codex-dispatcher\dispatcher.py --task "orchestrator plan Make a calculator" --plan-only
```

By default this starts only the planner worker through Codex app-server and
returns its task-specific proposal. Add `--dry-run` to test parser/log behavior
with the local fallback plan instead of launching Codex.

Approved local calculator demo project, no Codex app-server:

```powershell
python tools\codex-dispatcher\dispatcher.py --task "orchestrator plan Make a calculator" --local-test-project
```

Approved local construction-store CRM demo project, no Codex app-server:

```powershell
python tools\codex-dispatcher\dispatcher.py --task "orchestrator plan Make a CRM for a construction store" --local-test-project
```

Generated local demo projects are written under `test-projects/` by default and
are ignored by git. Supported demo projects are `calculator` and
`construction-crm`. Run `--local-test-project` only after the user has approved
the `--plan-only` proposal in chat.

For demo projects with a browser UI, reviewer output must include a `UI smoke`
section. The construction CRM smoke checks that navigation/action buttons have
a declared interaction contract and that the page loads JavaScript handlers, so
an inert static mock cannot pass as a working UI.

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
