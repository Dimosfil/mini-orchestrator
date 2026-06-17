# Local Chat Commands

## GI

- `gi start` / `ги старт`: compact startup restore.
- `gi help` / `ги команды`: show this local command list.

## Mini-Orchestrator

- `оркестратор <task>` / `orchestrator <task>`: route a task through the
  Codex-native dispatcher full chain.
- `оркестратор план <task>` / `orchestrator plan <task>`: start with a
  planner-directed task, then continue through executor and reviewer.
- `оркестратор исполнитель <task>` / `orchestrator executor <task>`: start with
  an executor-directed task, then continue through the full chain.
- `оркестратор ревью <task>` / `orchestrator review <task>`: start with a
  reviewer-directed task, then continue through the full chain.

For early chat tests, use dispatcher `--chain --dry-run` mode unless the user
explicitly asks to launch a real Codex worker.
