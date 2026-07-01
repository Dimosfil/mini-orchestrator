# Test Run Artifacts

## Purpose

Generated task results used for testing, smoke checks, demos, or visual
inspection must be kept as separate versions so earlier results remain
inspectable.

## Storage Contract

- Store task-generated artifacts under `.mini_orchestrator/test-runs/`.
- Use a stable task slug as the first folder level, for example:
  - `.mini_orchestrator/test-runs/calculator/`
  - `.mini_orchestrator/test-runs/rm/`
  - `.mini_orchestrator/test-runs/dental-crm/`
- Use a separate version folder for each task execution, such as `v001`,
  `v002`, or a timestamp like `2026-06-18_23-40-00`.
- Do not overwrite or delete older version folders during a new test run unless
  the user explicitly asks for cleanup.
- Orchestrator release-chain repeats that generate apps must use a
  project-named slug and version folder, for example
  `.mini_orchestrator/test-runs/dental-crm/v001/`, then
  `.mini_orchestrator/test-runs/dental-crm/v002/`.
- Do not modify `launch-desk/` or another existing application folder as the
  generated artifact target unless the user explicitly names that folder.
- A stable `latest` folder, link, or copy is optional and may be updated only
  when the user explicitly asks for a latest-style convenience target.

## Required Metadata

Each version folder should contain a short `README.md` or manifest that records:

- the original user task or test prompt;
- the run date/time;
- the main entry point, such as `index.html`, command, or generated script;
- verification performed;
- known gaps or failures.

## Current Implementation Map

- Agent instruction rule: `AGENTS.md`
- Default artifact root: `.mini_orchestrator/test-runs/`
- Symphony artifact contract enforcement:
  - `mini_orchestrator/symphony_daemon.py` allocates
    `.mini_orchestrator/test-runs/<slug>/<version>/` and injects the contract
    into Symphony intake and handoff payloads.
  - If a Symphony executor writes the app in its worker workspace,
    `mini_orchestrator/symphony_daemon.py` may materialize app-shaped workspace
    content into the allocated version folder while excluding service files such
    as `.env`, `.git`, `node_modules`, and `codex-workpad.md`.
  - `mini_orchestrator/ui.py` marks Mini-owned Symphony chains as failed when a
    completed chain does not produce generated files in the allocated version
    folder.
  - Mini-owned Symphony handoffs use `timeoutPerStepSeconds` as a soft timeout
    and `lateCompletionGraceSeconds` as an active-run grace window, so a long
    executor that is still running can complete and continue to QA/Risk/PM
    instead of cutting the chain immediately.
