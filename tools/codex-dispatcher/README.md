# Codex Dispatcher Prototype

This prototype is the Codex-native orchestration path for the mini-orchestrator.
It coordinates multiple Codex threads through `codex app-server` instead of
calling OpenAI models directly.

## Flow

1. Start Codex app-server as a subprocess.
2. Classify the user task into one worker role with a `DispatchDecision`.
3. Create one thread for the selected worker.
4. Send the selected worker the decision's `next_input`.
5. Return a dispatcher summary and write a JSONL event log.

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

Real Codex app-server run:

```powershell
python tools\codex-dispatcher\dispatcher.py --task "Implement the next scoped task"
```

Claim the next WorkNest task and route it through the dispatcher:

```powershell
$env:GI_CONFIG_SERVICE_URL = "http://127.0.0.1:4100"
python tools\codex-dispatcher\dispatcher.py --from-worknest --project mini-orchestrator
```

Generated runtime logs are written under `tools/codex-dispatcher/runs/` and are
ignored by git.

See `EVENT_PROTOCOL.md` for the JSONL event contract.
