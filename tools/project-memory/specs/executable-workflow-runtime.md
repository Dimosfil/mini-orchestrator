# Executable Workflow Runtime

Date: 2026-07-14

## Purpose

Mini Orchestrator owns workflow state, approval, routing, budgets, artifacts,
and human review. Codex Dispatcher, Symphony, and any future CrewAI integration
are execution adapters; none of them may become the source of truth for the
task lifecycle.

The canonical executable input is an immutable compiled agent-flow manifest.
The visual flow draft and a chain preset are authoring inputs, not mutable run
state.

## Runtime Contract

A compiled manifest contains:

- one approved snapshot for every agent node;
- a start node and explicit `success` / `failure` edges;
- bounded loop policy;
- runtime limits for steps, per-node retries, context artifacts, runtime, and
  per-node turns;
- the user-approved task context.

`mini_orchestrator.workflow_runtime.execute_manifest_graph` is the canonical
state machine for compiled manifests. It accepts an execution adapter callback
and does not call a model provider directly.

Every adapter returns a structured stage result:

```json
{
  "status": "success | failure | blocked",
  "summary": "bounded human-readable summary",
  "data": {},
  "artifacts": [],
  "issues": [],
  "verdict": "done | needs_changes | blocked | failed",
  "nextAgentId": "optional explicit route",
  "metrics": {
    "inputTokens": 0,
    "outputTokens": 0,
    "durationMs": 0
  }
}
```

The runtime converts each result into a versioned flow artifact. Downstream
nodes receive only the most recent `maxContextArtifacts` artifacts rather than
the full conversation history.

## Routing Rules

- `success` selects a `success` edge.
- `failure` selects a `failure` edge.
- `blocked` terminates the workflow as blocked.
- When a node has multiple edges for the same outcome, its result must provide
  `nextAgentId`; the runtime never asks an unbounded manager agent to guess.
- A failed node without a failure edge may retry up to
  `maxRetriesPerNode`.
- Failure/rework edges obey their compiled `maxIterations` limit.
- `maxWorkflowSteps` and `maxRuntimeSeconds` remain global safety stops even
  when every individual loop is bounded.

Successful terminal execution enters `review`, not final `done`. Only the
existing Human Review decision may accept the task into `done`.
`needs_changes` without an explicit failure/rework edge also enters Human
Review instead of leaving a non-resumable run falsely marked `retrying`.

## Checkpoint And Resume

Every node start, completion, route, retry, interruption, and terminal
transition checkpoints the full run state together with its event in one
SQLite transaction. The resumable pointer is `workflow.nextAgentId`.

If an adapter exits during a node:

1. the node is recorded as `interrupted`;
2. the next-agent pointer remains on that node;
3. resume creates a new attempt instead of pretending the interrupted attempt
   completed;
4. completed prior nodes and artifacts are not rerun.

## Integration Boundary

- The internal dry-run adapter is verification infrastructure, not a public
  product execution mode.
- Dispatcher and Symphony keep their current public endpoints while adapters
  are migrated to this state machine.
- A future CrewAI adapter may execute a bounded node or subflow, but it must
  return the same structured result and obey Mini Orchestrator limits.
- CrewAI memory, AMP, or another external control plane must not replace the
  SQLite run record or Human Review gate.

## Verification

Focused tests cover:

- linear manifest compatibility;
- structured artifacts and metrics;
- failure routing through QA rework;
- bounded-loop termination;
- atomic SQLite checkpoints;
- resume after an interrupted node.
