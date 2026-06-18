# Codex Dispatcher Event Protocol

Dispatcher runs write newline-delimited JSON to `tools/codex-dispatcher/runs/`.
Each event is one JSON object with at least:

- `time`: ISO-8601 UTC timestamp
- `type`: event type

When the dispatcher is started with `--run-id`, the JSONL filename must be
`<run-id>.jsonl`. UI clients may use that stable filename to poll live run
state before the subprocess prints its final JSON response.

## Event Types

- `task_created`: dispatcher accepted a user task.
- `dispatch_decision`: dispatcher selected one worker role for the task.
- `app_server_started`: Codex app-server subprocess started and initialized.
- `agent_thread_started`: a worker thread was created for one role.
- `handoff`: dispatcher sent prompt/context to a worker.
- `agent_turn_started`: worker turn was accepted by Codex.
- `codex_notification`: raw app-server notification captured for replay.
- `agent_started`: dry-run worker started.
- `agent_result`: worker returned a result.
- `final`: dispatcher assembled final worker outputs.
- `error`: dispatcher hit a terminal blocker.

Approval-gated Codex app-server turns are exposed through `codex_notification`
events whose raw method is `item/fileChange/requestApproval`. Replay consumers
should surface this as a blocked or `waiting_approval` state until a final or
terminal error event appears.

Chain runs use the same event types and add `chain=true` to task, dispatch, and
final events. Handoff and agent result events occur once per role in this order:
`planner`, `executor`, `reviewer`.

Plan-only runs use the same event types and add `planOnly=true`; they return
only planner output and must not write project files.

## Stable Fields

Worker-related events should include:

- `agent`: role name such as `planner`, `executor`, or `reviewer`
- `model`: model used by the worker when known
- `threadId`: Codex thread id when known
- `turnId`: Codex turn id when known
- `targetWorkspace`: project workspace the worker turn should operate on
- `workerChatRoot`: technical workspace used to group worker chats in Codex
- `processCwd`: app-server subprocess working directory when known

Task-related events should include:

- `task`: original user task or compact task summary
- `dryRun`: boolean when the run did not start Codex app-server
- `chain`: boolean when the run uses planner -> executor -> reviewer
- `planOnly`: boolean when the run returned only a chat approval plan

Dispatch decision events should include:

- `role`: selected worker role
- `reason`: short human-readable explanation
- `confidence`: numeric confidence from 0.0 to 1.0
- `next_input`: task text passed to the selected worker

Routing is conservative: planning markers select `planner`, explicit
implementation/editing markers select `executor`, explicit review/verification
markers select `reviewer`, and ambiguous requests fall back to `planner`.
In chain mode the dispatch decision still normalizes the user input, but the
dispatcher runs all chain roles in fixed planner -> executor -> reviewer order.

## Replay Rule

`codex_notification` may contain raw app-server payloads. Consumers should treat
those payloads as diagnostic evidence, not as the stable public protocol. The
stable replay surface is the normalized event type plus top-level fields.

## Privacy Rule

Runtime event logs are generated artifacts and are ignored by git. Do not commit
logs that include user prompts, model output, command output, local paths,
private data, or secrets.
