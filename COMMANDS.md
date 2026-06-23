# Local Chat Commands

## GI

- `gi start` / `ги старт`: compact startup restore.
- `gi start sprint` / `gi sprint start`: restore only task-manager context,
  resolve the configured manager, and request active Sprint/Cycle work through
  the documented manager contract.
- `gi help` / `ги команды`: show this local command list.
- `gi summary` / `gi саммари`: write a thematic thesis-based handoff summary
  under `tools/summary/`.
- `gi stack` / `ги стек`: find or build the current project's verified
  technology stack inventory.
- `gi test plan` / `gi тест-план`: inspect current local test contracts and
  produce a compact verification plan without running checks by default.
- `gi test task` / `ги тест таск`: set the active release/full-system
  verification workload for the next `gi test`.
- `gi test` / `ги тест`: run the current project's documented verification flow
  against the active test task.
- `gi default` / `gi defaults` / `ги дефолт`: reset the current project to its
  documented first-run/default state using only documented reset targets, then
  start and verify the default-state signals.
- `gi rebuild` / `ги ребилд`: rebuild the current project/application only,
  using documented project build instructions.
- `gi tools rebuild` / `gi rag rebuild`: rebuild the full configured
  GI/project-memory/RAG system after explicit confirmation.
- `gi tools rebuild sql|chunks|vector|manifest|evals` / `gi rag rebuild
  sql|chunks|vector|manifest|evals`: rebuild only that configured GI/RAG node.
- `gi refactor` / `gi рефактор` / `ги рефактор`: refactor the entire current
  project according to all applicable GI rules, in verified batches.
- `gi reboot` / `gi restart`: start or restart all documented project apps and
  report per-app verification evidence beyond PID creation.

## Mini-Orchestrator

- `оркестратор <task>` / `orchestrator <task>`: route a task through the
  Codex-native dispatcher full chain.
- `оркестратор план <task>` / `orchestrator plan <task>`: start with a
  planner-directed task, then continue through executor and reviewer.
- `оркестратор исполнитель <task>` / `orchestrator executor <task>`: start with
  an executor-directed task, then continue through the full chain.
- `оркестратор ревью <task>` / `orchestrator review <task>`: start with a
  reviewer-directed task, then continue through the full chain.

Chat `orchestrator` / `оркестратор` requests are real orchestration requests by
default. Do not use `--dry-run` for chat, smoke, release, or `gi test`
verification.
