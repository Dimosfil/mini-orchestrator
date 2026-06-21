# Agent Instructions For This Repository

This is the lightweight runtime entrypoint for this repository.

## Project

This workspace is the mini-orchestrator for AI-agent workflow experiments.
Use `README.md` and `tools/AGENT_WORKING_AGREEMENTS.md` for project-specific
behavior, integration contracts, runbook steps, stack details, and command
execution constraints.

## Fast Start

```powershell
.\tools\agent-start.ps1
```

If startup helpers are unavailable, read only the minimal slices requested by the
startup flow:

- `README.md`
- latest file in `tools/summary/`
- `tools/AGENT_WORKING_AGREEMENTS.md`
- `tools/AGENT_RUNBOOK.md`
- relevant notes in `tools/project-memory/`

## Loading Contract

- Start with this file.
- Read only the module(s) needed for the current request.
- For broad or unclear work, read these shared modules before acting:
  - `patterns/AGENTS_RUNTIME/01-purpose.md`
  - `patterns/AGENTS_RUNTIME/03-rule-precedence.md`
  - `patterns/AGENTS_RUNTIME/06-tool-usage-and-token-economy.md`
- If a task crosses topics, read every matching module first.

## Runtime Module Routing

- General runtime behavior, RAG startup, handoff summaries, connected projects:
  `patterns/AGENTS_RUNTIME/01-purpose.md`
- Repository map: `patterns/AGENTS_RUNTIME/02-repository-map.md`
- Rule precedence and scope arbitration:
  `patterns/AGENTS_RUNTIME/03-rule-precedence.md`
- Authoring reusable rules and boundaries:
  `patterns/AGENTS_RUNTIME/04-content-and-authoring.md`
- Windows commands/network policy:
  `patterns/AGENTS_RUNTIME/05-windows-command-policy.md`
- Token economy, scoped tool usage, verification lookup:
  `patterns/AGENTS_RUNTIME/06-tool-usage-and-token-economy.md`
- Startup, restoration, and scope boundaries:
  `patterns/AGENTS_RUNTIME/07-startup-and-scope.md`
- Config-service/task-manager flows:
  `patterns/AGENTS_RUNTIME/08-config-service-and-task-manager.md`
- Commands for reboot/summarize/update/tooling:
  `patterns/AGENTS_RUNTIME/09-project-operation-commands.md`
- Private-scope and missing context handling:
  `patterns/AGENTS_RUNTIME/10-private-scope-and-missing-context.md`
- Language preferences:
  `patterns/AGENTS_RUNTIME/11-language-preferences.md`
- UI and application focus:
  `patterns/AGENTS_RUNTIME/12-ui-and-focus.md`
- Progress updates and status language:
  `patterns/AGENTS_RUNTIME/13-progress-updates.md`
- Update intake and update-specific docs:
  `patterns/AGENTS_RUNTIME/14-update-intake.md`
- Verification policy:
  `patterns/AGENTS_RUNTIME/15-verification.md`
- Git and finalization:
  `patterns/AGENTS_RUNTIME/16-git-policy.md`

## Documentation / Project Memory Layers

- Use `README.md`, `docs/`, and runbooks for user-facing project context.
- Use `tools/project-memory/` for implementation-driving behavior, contracts,
  algorithms, and architectural guarantees.
- Prefer project-memory specs when implementing behavior changes and keep runtime
  behavior in one canonical stack and contracts path.

## Library Entrypoints

- `README.md`: high-level overview and user-facing command surface.
- `INDEX.md`: shared-instruction index and reusable file map.
- `COMMANDS.md`: compact GI command list.
- `CHANGELOG.md`: accepted instruction-kit change log.
- `VERSION.md`: accepted instruction-kit version.
- `templates/AGENTS.template.md`: reusable copied AGENTS template.

## Keep in Mind

Gi commands in this repository apply to this local project and use `AGENTS.md` as
the shared-instruction runtime entrypoint.

