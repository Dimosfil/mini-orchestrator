# Local Chat Commands

## GI

- `gi start` / `ги старт`: compact startup restore.
- `gi start sprint` / `gi sprint start`: restore only task-manager context,
  resolve the configured manager, and request active Sprint/Cycle work through
  the documented manager contract.
- `gi help` / `ги команды`: show this local command list.
- `gi summary` / `gi саммари`: write a thematic thesis-based handoff summary
  under `tools/summary/`.
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
default. Use `--dry-run` only when the user explicitly asks for parser/log smoke
testing.
