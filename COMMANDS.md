# Local Chat Commands

## GI

- `gi start` / `ги старт`: compact startup restore.
- `gi help` / `ги команды`: show this local command list.
- `gi summary` / `gi саммари`: write a thematic thesis-based handoff summary
  under `tools/summary/`.
- `gi rebuild` / `ги ребилд`: rebuild the current project/application only,
  using documented project build instructions.
- `gi tools rebuild` / `gi rag rebuild`: rebuild the full configured
  GI/project-memory/RAG system after explicit confirmation.
- `gi tools rebuild sql|chunks|vector|manifest|evals` / `gi rag rebuild
  sql|chunks|vector|manifest|evals`: rebuild only that configured GI/RAG node.
- `gi reboot` / `gi restart`: start or restart the current app and verify a
  startup success signal beyond PID creation.

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
