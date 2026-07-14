# CrewAI Workflow Runtime Adaptation Summary

Date: 2026-07-14

## Outcome

The CrewAI repository and two supplied Habr analyses were used as architecture
inputs, not copied as a dependency. The accepted decision is to keep Mini
Orchestrator as owner of task cards, approvals, routing, persistence, budgets,
and Human Review while treating Codex Dispatcher, Symphony, and any future
CrewAI integration as bounded execution adapters.

The first implementation batch added the missing project-owned Flow semantics:
compiled manifests now have a canonical graph state machine with structured
stage results, outcome routing, bounded retries and rework loops, context and
runtime limits, atomic SQLite state/event checkpoints, and resume after an
interrupted node.

## Local Mapping

- Visual flow and compiled manifest: authoring and immutable approval layers.
- `mini_orchestrator/workflow_runtime.py`: canonical executable graph contract.
- `mini_orchestrator/runtime_store.py`: atomic run/event checkpoint owner.
- `mini_orchestrator/daemon_runs.py`: internal verification adapter and resume
  integration; it does not restore the retired public dry-run endpoint.
- Dispatcher and Symphony: current product execution modes and future node
  adapters around the canonical runtime.
- CrewAI: researched external framework and possible future optional adapter,
  not an installed runtime dependency.

## Decisions

- Do not replace Mini Orchestrator with CrewAI.
- Do not use an unrestricted manager agent or unbounded delegation for routing.
- When one outcome has several possible edges, require structured
  `nextAgentId` rather than an implicit LLM decision.
- Keep durable runtime state in project SQLite, not CrewAI memory or AMP.
- Keep successful and `needs_changes` terminal results behind Human Review.
- Limit downstream context to recent structured artifacts instead of copying
  the whole conversation.

## Follow-up

Dispatcher and Symphony currently retain their existing public endpoints and
business behavior. Their node execution can be migrated incrementally to the
canonical manifest runtime, but that migration must preserve the approved
Dashboard workflow and one-task-card ownership contract. A CrewAI adapter is a
hypothesis for a later isolated spike and must not be added until its Python
runtime and operational cost are explicitly accepted.
