# Handoff Summary: Symphony-style WorkNest agent cards

Date: 2026-06-18 20:16:27
Thread topic: Connecting mini-orchestrator visual agent cards, WorkNest tasks,
and a Symphony-style Codex app-server daemon.

## User Intent

The user recognized that mini-orchestrator's visual agent cards can become the
human-editable worker profiles that a Symphony-style daemon manages. The goal is
not to adopt Linear or copy Symphony wholesale; the goal is to use Symphony's
daemon lifecycle pattern with WorkNest as the local task source and
mini-orchestrator as the builder/planner/monitoring surface.

## Core Architecture Thesis

The intended system is:

```text
WorkNest task
  -> mini-orchestrator planner / UI approval
  -> card or card-flow selection
  -> worker profile compiler
  -> Symphony-style daemon
  -> Codex app-server worker in isolated workspace
  -> event/status/tokens/result
  -> WorkNest + mini-orchestrator UI
```

Important decisions:

- WorkNest replaces Linear as the source of work.
- Agent cards become worker profile inputs, not independent runtime processes.
- The daemon owns lifecycle after approval: claim, workspace, Codex
  app-server worker, events, retries, blocked state, completion.
- Symphony remains a read-only reference workspace unless the user explicitly
  approves edits there.
- The daemon should use Codex app-server, matching both current Symphony and
  mini-orchestrator's existing dispatcher path.

## Symphony Reference Findings

`D:\AI\symphony` is registered in the connected-projects GI register.

Current Symphony reference implementation has one workflow-defined Codex worker
profile and can run many parallel instances through `agent.max_concurrent_agents`.
It does not currently have mini-orchestrator-style named cards such as planner,
executor, reviewer, QA, and release. That makes mini-orchestrator's card system
a useful extension: cards can supply multiple worker profiles while Symphony's
pattern supplies lifecycle management.

Current Symphony launches agents through `codex app-server`; it does not make
direct OpenAI API calls from the daemon. API keys may still be used by Codex's
runtime/auth environment, but the daemon talks to Codex app-server protocol.

## Connected Projects Register

Updated `tools/project-memory/specs/integration-contracts/connected-projects.md`
with:

- `D:\AI\LaunchDeskOpenAI`
- `D:\AI\WorkNest`
- `D:\AI\AiAnalytics\token-lens`

Also enriched the existing `D:\AI\symphony` entry with
`https://github.com/openai/symphony.git`.

Privacy boundaries were recorded:

- WorkNest may contain task-manager data and credential-shaped files.
- Token Lens reads Codex usage/log metadata and has private analytics data.
- Symphony is read-only for this project unless explicitly approved otherwise.

## Durable Plan Created

Created `tools/project-memory/symphony-worknest-agent-card-plan.md`.

It includes:

- feature idea;
- functional description;
- current reference facts;
- workflow contract;
- proposed architecture;
- data model sketches for worker profile snapshots and run records;
- sprint breakdown from contracts through multi-agent flow execution;
- risks and controls;
- open decisions;
- first implementation slice.

The first implementation slice is deliberately small:

1. Backend agent-flow persistence and card validation.
2. Compile one card into a worker profile snapshot.
3. Resolve WorkNest through config-service and read guide/contract.
4. Run a dry-run daemon lifecycle without launching Codex.
5. Add UI status for that dry-run run record.

## WorkNest Sprint Intake

Resolved WorkNest through GI config-service:

- service id: `worknest`
- base URL from config-service: `http://127.0.0.1:4187`
- contract: `/agent-intake/contract`
- API: `/agent-intake`

Created an active WorkNest sprint through `POST /agent-intake/raw` using
`type: "plan"`.

Intake id:
`2026-06-18T17-03-13-702Z_codex_e3c6ed31-c299-4ece-8da8-ab0f8f3133b5`

Sprint id:
`2026-06-18_20-03-13_спринт-карточки-агентов-как-worker-профили-agent-cards-as-symphony-style-worker-`

Sprint status returned by WorkNest: `active`.

Created five tasks:

1. `Контракты WorkNest и daemon / WorkNest and daemon contracts`
2. `Backend-контракт карточек / Agent card backend contract`
3. `Worker profile snapshot / Worker profile snapshot`
4. `Run state daemon / Daemon run state`
5. `Форма daemon MVP / Daemon MVP shape`

## WorkNest Card Correction

The first accepted intake payload used text items. WorkNest accepted it, but it
produced overly long card titles because detailed `What to do` and
`Definition of done` text was embedded in the item title.

The manager contract says:

- card title should be short Russian title plus English duplicate;
- detailed implementation instructions belong in `What To Do`;
- criteria belong in `Definition Of Done`;
- object-shaped plan items should use `title` plus `titleRu/titleEn`, with
  `body` for details and `done` or `acceptance` for criteria.

The generated WorkNest task markdown files were corrected in place to match the
title policy. Metadata was preserved except for one accidental check:
calling `/agent-intake/next-task` marked task 001 as `in_progress`; this was
immediately reverted to `Status: todo` and `StartedAt: none`.

Read-only verification after correction showed all five tasks as `Status: todo`
and `StartedAt: none`, with compact headings and no `What to do:` or
`Definition of done:` in headings.

## Useful Next Context

Use `tools/project-memory/symphony-worknest-agent-card-plan.md` as the contract
source before implementing.

Use WorkNest through config-service and contract endpoints. Do not hard-code
`http://127.0.0.1:4187` in code.

Do not use `/agent-intake/next-task` as a read-only inspection endpoint; it can
claim/start a task. For passive inspection, read task files only when the user
has explicitly allowed the WorkNest path or use documented read-only manager
endpoints when they exist.

If creating future WorkNest plan payloads, prefer object items with this shape:

```json
{
  "title": "WorkNest and daemon contracts",
  "titleRu": "Контракты WorkNest и daemon",
  "titleEn": "WorkNest and daemon contracts",
  "body": "Detailed What To Do text.",
  "done": "Definition Of Done text."
}
```

## Current Worktree Notes

Known local changes from this thread:

- modified `tools/project-memory/specs/integration-contracts/connected-projects.md`;
- added/modified `tools/project-memory/symphony-worknest-agent-card-plan.md`;
- added this summary file;
- WorkNest external project task files were edited under
  `D:\AI\WorkNest\projects\mini-orchestrator\sprints\...` to fix card titles.

There were unrelated pre-existing dirty files before this work, including
`AGENTS.md`, `tools/AGENT_WORKING_AGREEMENTS.md`, and a prior summary file.
