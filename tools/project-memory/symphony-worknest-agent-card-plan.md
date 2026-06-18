# Symphony-Style WorkNest Agent Card Plan

Date: 2026-06-18

## WorkNest Intake

- Intake id:
  `2026-06-18T17-03-13-702Z_codex_e3c6ed31-c299-4ece-8da8-ab0f8f3133b5`.
- WorkNest sprint id:
  `2026-06-18_20-03-13_спринт-карточки-агентов-как-worker-профили-agent-cards-as-symphony-style-worker-`.
- Status returned by `/agent-intake/raw`: `ready`, `sprintStatus=active`.
- Payload note: WorkNest rejected object-shaped `items` with
  `Plan payload must contain non-empty items or numbered body text`; the
  accepted payload used `type=plan` and text items.
- Correction note: the accepted text items produced overly long card titles.
  The generated WorkNest task files were corrected on 2026-06-18 to match the
  manager title policy: compact RU/EN titles, details in `What To Do`, and
  criteria in `Definition Of Done`.

## Feature Idea

Turn visual agent cards into executable worker profiles for a Symphony-style
daemon. WorkNest is the source of work, mini-orchestrator is the UI/planning
surface, and the daemon owns worker lifecycle, isolated workspaces, retries,
blocked state, runtime events, and token/status observability.

The target replaces the Symphony reference implementation's Linear dependency
with a WorkNest tracker adapter while preserving the useful Symphony pattern:
long-running orchestration over Codex app-server workers.

## Functional Description

Users configure agent cards in mini-orchestrator. A card contains role,
instructions, model, reasoning, speed, allowed actions, constraints, expected
output, and work-package fields. When a WorkNest task is selected for execution,
mini-orchestrator chooses a card or card flow and compiles it into a worker
profile. A Symphony-style daemon runs the chosen worker through Codex
app-server in an isolated workspace and reports status back to WorkNest and the
mini-orchestrator UI.

The first production shape should not depend on Linear. WorkNest owns task
identity, state, descriptions, workpads, and final result records. A future
adapter may keep the Symphony tracker interface but implement it over WorkNest
operations.

## Current Reference Facts

- `D:\AI\symphony` is registered in the connected-projects GI register as an
  approved read-only reference workspace for mini-orchestrator design.
- Current Symphony Elixir uses one workflow-defined Codex worker profile, not a
  set of named agent cards.
- Current Symphony can run many parallel instances of that worker profile
  through `agent.max_concurrent_agents`.
- Current Symphony launches workers through `codex app-server`, not direct
  OpenAI API calls from the daemon.
- Current mini-orchestrator already has Codex app-server based dispatcher and
  visual-agent mini-chat paths.
- Current visual cards are persisted in browser localStorage and are not yet a
  backend-executable contract.

## WorkNest Service Contract Snapshot

Verified on 2026-06-18 through GI config-service:

- Task-manager service id: `worknest`.
- Config-service lookup: `GET /services/worknest`.
- WorkNest availability endpoint: `endpoints.availability`.
- WorkNest strict contract endpoint: `endpoints.contract`.
- WorkNest agent API root: `endpoints.api`.
- No guide endpoint was advertised in the service record at verification time,
  so the strict contract endpoint is the current agent-facing authority.
- Advertised capabilities:
  - `task-intake`
  - `plan-intake`
  - `next-task`
  - `task-completion`

Application and daemon code must resolve the concrete URLs at startup through
config-service. The URLs observed during verification are not source-code
constants.

## WorkNest-To-Daemon Lifecycle Map

The current WorkNest contract supports a narrow external-agent lifecycle:

| Daemon need | Current WorkNest operation | Contract status |
| --- | --- | --- |
| Resolve task-manager runtime | `GET /services/worknest` through config-service, then read `endpoints.contract` and `endpoints.api` | Supported |
| Submit a plan or sprint intake | `POST /agent-intake/raw` as documented by `taskMovementPolicy.externalAgents` | Supported by contract text |
| Request/claim assigned work | `GET /agent-intake/next-task?project=<project>` | Supported; WorkNest dispatcher owns the status move and may return an `in_progress` task |
| Complete work | `POST /agent-intake/task-completed` with `status/resultStatus/outcome=done` | Supported |
| Report blocked work | `POST /agent-intake/task-completed` with `status/resultStatus/outcome=blocked` or `blocked=true` | Supported |
| Edit product work-item cards | `/agent-intake/work-items` list/read/create/update routes | Supported for work items, not sprint task movement |
| List all dispatchable sprint tasks | No explicit external-agent endpoint found beyond `next-task` | Blocker for dashboard-style queues unless WorkNest adds a read endpoint |
| Write incremental progress/workpad updates for sprint tasks | No documented sprint-task progress or workpad update endpoint found | Blocker for live daemon progress reporting |
| Arbitrary task status transitions | Forbidden for external agents | Intentionally unsupported; WorkNest manager owns movement |
| Archive sprints directly | Forbidden for external agents | Intentionally unsupported; WorkNest dispatcher owns archive movement |

Daemon integration must therefore treat `next-task` as the claim/request
boundary and `task-completed` as the only documented terminal sprint-task write.
Anything richer, such as progress messages, token updates, workpad appends, or
queue dashboards, needs a new WorkNest contract capability before production
code depends on it.

## Daemon MVP Shape Decision

Decision for the first MVP: implement the Symphony-style daemon as an
application-owned Python runtime component inside the existing
`mini-orchestrator` process, not as a separate local HTTP service.

Rationale:

| Concern | In-process Python component | Separate registered service |
| --- | --- | --- |
| Startup rules | Reuses the existing mini-orchestrator UI startup and config-service lookup; no new port is bound | Requires a new service id, config-service record, guide/contract, health endpoint, and no fallback binding |
| Testability | Can be unit-tested with fake WorkNest and fake Codex transports without network setup | Better process isolation but more integration harness work |
| WorkNest integration | Can reuse the same config-service-resolved `worknest` client contract | Same requirement, plus cross-service retry and health semantics |
| UI observability | UI can read in-process run state through existing mini-orchestrator API routes | UI must resolve and proxy another service safely |
| Failure recovery | Worker failures can be represented in run state first; process isolation can come later | Stronger isolation, but premature before one-task dry-run lifecycle exists |

First implementation slice:

1. Add backend flow persistence and validation.
2. Compile one validated card into a worker profile snapshot.
3. Add an in-process daemon runner module with fake/dry-run WorkNest and Codex
   transports for tests.
4. Produce a daemon run-state record without launching real Codex.
5. Expose the run-state record through the existing mini-orchestrator UI/API
   after config-service startup succeeds.

No daemon MVP code may bind a fallback port, read WorkNest storage directly, or
use stale endpoint records. If the daemon later becomes a separate service, that
new service must be registered through config-service before it binds.

## Agent Card Backend Contract

The browser-local flow model is design state. It becomes executable only after
the backend stores it, validates it, and compiles an immutable worker profile
snapshot for an approved run.

### API Shape

Initial backend endpoints:

- `GET /api/agent-flows`
  - Lists saved flow summaries: `id`, `name`, `version`, `updatedAt`,
    `validationStatus`.
- `POST /api/agent-flows`
  - Creates a saved flow from a `FlowDraft`.
- `GET /api/agent-flows/{id}`
  - Reads a saved flow and its latest validation result.
- `PUT /api/agent-flows/{id}`
  - Replaces the draft flow and increments `version`.
- `POST /api/agent-flows/{id}/validate`
  - Returns `valid`, `errors`, `warnings`, normalized flow metadata, and start
    node candidates.
- `POST /api/agent-flows/{id}/compile`
  - Requires a valid flow, selected start node or execution path, and explicit
    approval metadata. Produces immutable worker profile snapshots and a run
    manifest draft. It must not start Codex workers by itself.

`POST /api/agent-flows/{id}/run` remains a future endpoint. Runtime dispatch
should be added only after compile output, WorkNest task mapping, daemon service
lookup, and user approval are all explicit.

### Stored Flow Schema

```json
{
  "id": "flow-...",
  "name": "Planner / Executor / Reviewer",
  "version": 1,
  "agents": [],
  "connections": [],
  "presetSettings": {},
  "createdAt": "2026-06-18T00:00:00Z",
  "updatedAt": "2026-06-18T00:00:00Z",
  "validation": {
    "status": "unknown|valid|invalid",
    "checkedAt": null,
    "errors": [],
    "warnings": []
  }
}
```

### Agent Card Schema

```json
{
  "id": "agent-...",
  "name": "Executor 1",
  "preset": "executor",
  "role": "Executor",
  "llm": "gpt-5.4",
  "speed": "balanced",
  "reasoning": "medium",
  "workPackage": {
    "instructions": "...",
    "currentObjective": "...",
    "inputsArtifacts": "...",
    "constraints": "...",
    "previousOutputs": "...",
    "allowedTools": "...",
    "expectedOutput": "..."
  },
  "workPackageTranslations": {},
  "x": 240,
  "y": 160
}
```

Required fields are `id`, `name`, `role`, `llm`, `speed`, `reasoning`, and
`workPackage`. The backend may preserve `preset`, translations, and coordinates
as UI state, but compiled worker profile snapshots must use only validated
runtime fields and approved prompt fields.

### Connection Schema

```json
{
  "id": "connection-...",
  "fromAgentId": "agent-...",
  "toAgentId": "agent-...",
  "fromPort": "success",
  "toPort": "input"
}
```

Allowed `fromPort` values are `success` and `failure`. Allowed `toPort` value is
`input`.

### Validation Rules

- Flow must contain at least one agent.
- Agent ids and connection ids must be unique inside the flow.
- Every connection endpoint must reference an existing agent.
- Connections must use only supported ports.
- `llm`, `speed`, and `reasoning` must be in the supported runtime allowlists.
- Required work-package fields must be strings. Empty strings are allowed for
  drafts but rejected during compile for fields required by the selected role.
- A compile request must identify a start node or validate exactly one start
  node from graph topology.
- Cycles are invalid until an explicit loop policy exists.
- Browser `localStorage` state must be imported as a draft, not trusted as an
  executable runtime contract.
- Validation must return precise field paths so the UI can focus the broken
  card, connection, or work-package field.

### Compile Output

Compile produces immutable snapshots rather than mutating the saved flow:

```json
{
  "manifestId": "run-manifest-...",
  "flowId": "flow-...",
  "flowVersion": 1,
  "profileSnapshots": [],
  "graph": {
    "startAgentId": "agent-...",
    "connections": []
  },
  "runtimePolicy": {
    "requiresUserApproval": true,
    "startsWorkers": false
  }
}
```

The daemon may consume this manifest after a WorkNest task is selected and the
user approves dispatch. The saved flow remains editable design state; the
manifest is the execution input.

## Workflow Contract

1. WorkNest remains the source of truth for tasks.
2. Mini-orchestrator remains the human-facing builder, planner, approval, and
   monitoring UI.
3. Agent cards are treated as worker profile inputs, not as independent runtime
   processes.
4. The daemon owns execution lifecycle after approval:
   - claim task;
   - prepare isolated workspace;
   - start or reuse a Codex app-server worker;
   - send the compiled card work package as prompt/developer context;
   - collect events, token totals, tool status, and final messages;
   - update task state, workpad, and result through WorkNest;
   - retry, block, continue, or finish according to configured policy.
5. The daemon must not read private WorkNest storage directly when a service
   API/contract is available. Resolve WorkNest through GI config-service and use
   documented guide/contract endpoints.
6. The daemon must not hard-code ports, local service URLs, credentials, model
   names that are deployment choices, workspace roots, or task-manager paths.
7. The external `D:\AI\symphony` checkout is reference-only unless the user
   explicitly approves edits there.
8. Generated runtime logs, workspaces, Codex session artifacts, and private
   task data are not durable project-memory specs.

## Proposed Architecture

```text
WorkNest task
  -> mini-orchestrator planner / UI approval
  -> card or card-flow selection
  -> worker profile compiler
  -> Symphony-style daemon
  -> Codex app-server worker in isolated workspace
  -> event/status/tokens/result
  -> WorkNest workpad + mini-orchestrator UI
```

### Main Components

- `WorkNest tracker adapter`
  - Lists dispatchable tasks.
  - Claims a task.
  - Reads title, description, state, labels/tags, workpad, links, and
    acceptance criteria.
  - Writes status transitions, workpad updates, blocked reasons, result
    summaries, artifact links, and completion state.

- `Agent card backend contract`
  - Persists card and flow definitions server-side.
  - Validates model, reasoning, allowed tools, constraints, expected output, and
    graph connections.
  - Produces immutable worker profile snapshots for approved runs.

- `Worker profile compiler`
  - Converts a card or flow node into Codex app-server runtime settings and
    prompt/developer instructions.
  - Maps card fields to model/reasoning/sandbox/prompt/allowed actions.
  - Emits a compact run manifest for replay and debugging.

- `Symphony-style daemon`
  - Polls WorkNest or accepts an explicit refresh/dispatch signal.
  - Enforces concurrency limits.
  - Creates isolated workspaces per task/run.
  - Runs Codex app-server workers.
  - Tracks running, retrying, blocked, done, and failed states.
  - Exposes observability API for mini-orchestrator.

- `Mini-orchestrator UI`
  - Shows WorkNest tasks, selected card/flow, run state, active worker,
    workspace, recent events, token totals, retry queue, and blocked reasons.
  - Provides explicit approval before dispatching a task into the daemon.

## Data Model Sketch

### Worker Profile Snapshot

Machine-readable schema:
`tools/project-memory/specs/agent-worker-profile-snapshot.schema.json`.
Parseable example:
`tools/project-memory/specs/agent-worker-profile-snapshot.example.json`.

```json
{
  "schemaVersion": 1,
  "snapshotId": "profile-snapshot-...",
  "source": {
    "flowId": "flow-...",
    "flowVersion": 1,
    "sourceCardId": "agent-...",
    "compiledAt": "2026-06-18T00:00:00Z",
    "approvalId": "approval-..."
  },
  "displayName": "Executor 1",
  "role": "Executor",
  "model": {
    "name": "gpt-5.4",
    "reasoning": "medium",
    "speed": "balanced"
  },
  "workPackage": {
    "instructions": "...",
    "currentObjective": "...",
    "inputsArtifacts": "...",
    "constraints": "...",
    "previousOutputs": "...",
    "allowedTools": "...",
    "expectedOutput": "..."
  },
  "runtimePolicy": {
    "sandboxMode": "workspace-write",
    "approvalPolicy": "never",
    "networkAccess": true,
    "workspaceRootPolicy": "isolated-generated-workspace",
    "maxTurns": 12
  },
  "codexAppServer": {
    "workerName": "executor",
    "developerInstructions": "Role, constraints, allowed actions, and output contract compiled from the approved card.",
    "initialUserMessage": "WorkNest task context plus current objective and expected output."
  }
}
```

A snapshot is immutable after compile. The daemon passes `model.name`,
`model.reasoning`, and `codexAppServer.developerInstructions` into the Codex
app-server thread configuration, then sends `codexAppServer.initialUserMessage`
as the first user turn. The saved card remains editable design state and must
not be mutated by worker execution.

### Run Record

Machine-readable schema:
`tools/project-memory/specs/daemon-run-state.schema.json`.
Parseable example:
`tools/project-memory/specs/daemon-run-state.example.json`.

```json
{
  "schemaVersion": 1,
  "runId": "run-...",
  "task": {
    "taskId": "worknest-task-...",
    "sprintId": "sprint-...",
    "project": "mini-orchestrator"
  },
  "profileSnapshotId": "profile-snapshot-...",
  "status": "running",
  "workspacePath": "generated-workspaces/run-...",
  "thread": {
    "threadId": "codex-thread-...",
    "currentTurnId": "codex-turn-...",
    "turnCount": 1
  },
  "tokens": {
    "input": 0,
    "output": 0,
    "total": 0
  },
  "lastEvent": "...",
  "lastError": null,
  "artifacts": {
    "eventLogPath": "runtime/daemon-runs/run-....jsonl",
    "workspaceGenerated": true,
    "durableProjectMemory": false,
    "privateRuntimeData": true
  },
  "createdAt": "2026-06-18T00:00:00Z",
  "updatedAt": "2026-06-18T00:01:00Z"
}
```

Run states:

- `queued`: run manifest exists, but no WorkNest task has been claimed and no
  Codex worker is active.
- `claimed`: WorkNest task has been issued by `next-task`; daemon is preparing
  workspace and worker context.
- `running`: Codex app-server worker has an active thread or turn.
- `retrying`: previous worker attempt failed under a retryable policy and the
  daemon is preparing another bounded attempt.
- `blocked`: execution needs user input, a missing service capability,
  approval, credentials, or another external state change. Report to WorkNest
  with blocked completion when the task cannot continue.
- `done`: daemon produced accepted final output and reported completion to
  WorkNest.
- `failed`: daemon hit a non-retryable infrastructure or contract error before
  a reliable blocked/done result could be reported.

Allowed transitions:

```text
queued -> claimed -> running -> done
queued -> claimed -> running -> blocked
queued -> claimed -> running -> retrying -> running
queued -> claimed -> failed
claimed -> blocked
running -> failed
retrying -> blocked
retrying -> failed
```

Generated logs, temporary workspaces, Codex session artifacts, raw prompts, raw
task payloads, and private runtime data are operational artifacts. They may be
referenced by id or redacted summary in project memory, but they are not durable
project-memory specifications and should remain ignored or stored in a
configured generated runtime area.

## Sprint Breakdown

### Sprint 0: Contracts And Boundaries

Goal: make the integration executable on paper before code changes.

Tasks:

- [x] Record WorkNest service guide/contract endpoints through config-service.
- [x] Define backend storage contract for agent cards and flows.
- [x] Define worker profile snapshot schema.
- [x] Define daemon run state schema.
- [x] Decide whether the daemon lives inside mini-orchestrator first or as a
      separate local service.
- [x] Record generated artifact paths that must stay ignored.

Definition of done:

- [x] All runtime URLs are resolved through config-service.
- [x] No Linear dependency remains in the target contract.
- [x] No external `D:\AI\symphony` edits are required.

Verification:

- [x] Read WorkNest service record and contract through config-service.
- [!] WorkNest service record did not advertise a guide endpoint; use the
      strict contract endpoint until a guide is added.
- [x] Validate JSON schema examples with a small local parser/test.

### Sprint 1: Read-Only Symphony/Daemon Status Bridge

Goal: let mini-orchestrator observe a Symphony-style daemon without dispatching
work yet.

Tasks:

- [ ] Add `symphony` or `mini-orchestrator-daemon` service lookup through
      config-service.
- [ ] Add client for `GET /api/v1/state`.
- [ ] Add client for `GET /api/v1/<task_or_issue_identifier>`.
- [ ] Add client for `POST /api/v1/refresh`.
- [ ] Add mini-orchestrator API proxy endpoints under `/api/daemon/*`.
- [ ] Add UI panel for running/retrying/blocked/done summary.

Current MVP note:

- [x] Added a read-only `/api/daemon/runs` endpoint backed by local demo
      run-state records shaped like `daemon-run-state.v1`.
- [x] Added a main dashboard `Live Runs` section showing active, blocked,
      done, and total counts plus run cards with profile, status, tokens,
      thread, log, and last event/error.
- [x] Marked the endpoint as `read-only-demo` in the mini-orchestrator
      service contract. This MVP does not claim WorkNest tasks, query a daemon
      service, bind another port, or launch Codex workers.

Definition of done:

- [ ] UI can show daemon state from a configured service.
- [ ] Missing service record produces a clear blocker.
- [ ] No fallback port guessing exists.

Verification:

- [ ] Unit tests for daemon client success and JSON error envelopes.
- [ ] UI/API smoke against a mocked daemon endpoint.

### Sprint 2: Agent Cards Become Backend Worker Profiles

Goal: move cards from browser-local design artifacts toward executable worker
profile snapshots.

Tasks:

- [ ] Add backend persistence endpoints for agent flows.
- [ ] Validate card fields and graph connections server-side.
- [ ] Add profile compiler from card to worker profile snapshot.
- [ ] Store immutable profile snapshots for approved runs.
- [ ] Keep mini-chat separate from execution history.

Definition of done:

- [ ] A saved card can compile into a worker profile snapshot.
- [ ] Unsupported model/reasoning/tool settings are rejected before execution.
- [ ] Flow execution still requires explicit approval.

Verification:

- [ ] Focused tests for validation and profile compilation.
- [ ] Browser smoke for save/load/compile path.

### Sprint 3: WorkNest Tracker Adapter

Goal: replace Linear-shaped work intake with WorkNest-shaped task intake.

Tasks:

- [ ] Resolve `worknest` service through config-service.
- [ ] Read WorkNest guide endpoint, then strict contract endpoint.
- [ ] Implement task listing for dispatchable states.
- [ ] Implement claim/update/block/complete operations using documented API.
- [ ] Map WorkNest states to daemon states.
- [ ] Map WorkNest workpad/result fields to agent prompt context.

Definition of done:

- [ ] Daemon can read and claim a WorkNest task without direct filesystem reads.
- [ ] Daemon can write progress and final result back through WorkNest API.
- [ ] Missing capability stops with an exact blocker.

Verification:

- [ ] Contract tests against a fake WorkNest service.
- [ ] One dry-run task lifecycle without launching Codex.

### Sprint 4: Local Symphony-Style Daemon MVP

Goal: run one approved WorkNest task through one compiled card profile.

Tasks:

- [ ] Add daemon loop or daemon service entrypoint.
- [ ] Add isolated workspace creation under configured generated root.
- [ ] Launch Codex app-server with compiled model/reasoning/runtime policy.
- [ ] Send first prompt from WorkNest task plus worker profile snapshot.
- [ ] Stream and record runtime events.
- [ ] Report status/tokens/result to WorkNest and UI.
- [ ] Implement blocked state for approval/input/tool failures.

Definition of done:

- [ ] One task can run from queued to done or blocked.
- [ ] Workspace stays inside configured generated root.
- [ ] Event log is replayable enough for UI/debug.
- [ ] User-visible task status updates land in WorkNest.

Verification:

- [ ] Unit tests for state transitions.
- [ ] Dry-run app-server transport test.
- [ ] One manual smoke with a harmless task and generated workspace.

### Sprint 5: Multi-Agent Card Flow Execution

Goal: execute visual card flows as routed worker profiles.

Tasks:

- [ ] Identify start nodes and branch rules.
- [ ] Execute success/failure edges.
- [ ] Pass previous agent outputs as structured artifacts, not full chat logs.
- [ ] Enforce per-flow and per-card concurrency limits.
- [ ] Add retry policy per card or per flow.
- [ ] Add reviewer/validator card support before final completion.

Definition of done:

- [ ] Planner -> executor -> reviewer flow can run from saved cards.
- [ ] Failure branch can route to a repair/retry card.
- [ ] UI shows each node's run state and output.

Verification:

- [ ] Graph validation tests.
- [ ] Simulated flow runner tests.
- [ ] Manual smoke with a three-card flow.

## Risks And Controls

- Risk: card prompts become too weak for unattended execution.
  - Control: compile cards into explicit worker profile snapshots with required
    constraints, allowed actions, and expected output.

- Risk: WorkNest private data leaks into project memory or logs.
  - Control: store only task IDs, statuses, and redacted summaries in durable
    mini-orchestrator docs; keep raw task data in WorkNest.

- Risk: daemon and UI disagree on task state.
  - Control: WorkNest is the source of truth; daemon runtime state is
    operational and can be reconstructed or marked stale.

- Risk: unbounded worker actions.
  - Control: enforce workspace root containment, sandbox policy, allowed action
    policy, and explicit approval before dispatch.

- Risk: Symphony reference implementation is Linear-shaped.
  - Control: treat `D:\AI\symphony` as a reference for lifecycle and
    observability, not as a required dependency or direct fork target.

## Open Decisions

- Should the first daemon live inside the existing Python UI process, or as a
  separate service registered through config-service?
- Should WorkNest push tasks to the daemon, or should the daemon poll WorkNest?
- Which card fields become developer instructions versus user prompt content?
- Which runtime policies are editable in the UI and which remain project-owned
  safety defaults?
- Which generated logs are safe to expose in UI without leaking prompt content?

## First Implementation Slice

The smallest useful implementation should be:

1. Add backend agent-flow persistence and card validation.
2. Compile one card into a worker profile snapshot.
3. Resolve WorkNest through config-service and read its guide/contract.
4. Run a dry-run daemon lifecycle that claims a fake or test task and produces
   a run record without launching Codex.
5. Add UI status for that dry-run run record.

This slice proves the architecture without committing to the full Symphony
daemon or touching the external Symphony checkout.
