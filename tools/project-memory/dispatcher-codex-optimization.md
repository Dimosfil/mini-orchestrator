# Dispatcher/Codex Worker Optimization Notes

## Current Active Path

Visual-agent UI LLM requests use the dispatcher/Codex app-server path as the
primary runtime channel:

1. The UI endpoint calls `VisualAgentApi`.
2. `VisualAgentApi` writes a temporary UTF-8 task file.
3. The UI starts `python tools/codex-dispatcher/dispatcher.py`.
4. The dispatcher starts `codex app-server`.
5. The dispatcher starts a Codex thread for the selected worker.
6. The dispatcher sends one turn and waits for the final agent message.

This path works without a project `OPENAI_API_KEY` because Codex app-server uses
the local Codex/ChatGPT authenticated environment, not this project's OpenAI API
client.

## Latency Sources

- Process startup: one Python dispatcher process per UI request.
- Codex startup: one `codex app-server` process per dispatcher run.
- Thread startup: one Codex thread per worker request.
- Prompt overhead: generic worker prompts are larger than short UI-helper tasks.
- Model choice: translation must use a stable application-owned helper model,
  not the model selected on the visual workflow card.
- Browser behavior: blur-triggered translations can create repeated calls while
  editing multiple fields.

## Optimization Options

- Keep one dispatcher service alive inside the UI process and reuse a running
  `codex app-server` instead of starting it per request.
- Add a persistent worker/thread cache for short helper tasks. Reuse one
  planner/helper thread when isolation requirements allow it.
- Add a dedicated `helper` worker profile with a small prompt, low reasoning,
  and a fast model for translation and UI text polishing.
- Do not add transient translation cache. Future durable storage should record
  successful translations in the project database; when the source text differs
  from the recorded current text, treat it as a new translation request.
- Debounce or batch blur-triggered translations in the browser so saving a
  settings dialog does not launch several sequential worker calls.
- Add latency events around dispatcher process start, app-server initialize,
  thread start, turn start, and turn complete. Optimize from measured timings
  rather than wall-clock guesses.

## Recommended Next Increment

Start with measurement and the least invasive runtime changes:

1. Add timing events to the dispatcher and UI wrapper.
2. Introduce a reusable app-server manager owned by the UI process.
3. Add a dedicated lightweight translation/helper worker profile.
4. If latency remains high, consider helper-thread reuse after measuring
   context contamination risks.

The reusable app-server manager has the largest expected speedup, but it also
changes lifecycle and failure handling. It should preserve the current clear
fallback behavior: if the persistent server dies, restart it once and surface a
clear UI error if the retry fails.

## Current Increment

The UI now creates one `PersistentCodexDispatcher` for the server lifetime.
Single-worker helper requests can reuse the same `codex app-server` process.
Plan-only, dry-run, and full-chain workflows still use the older subprocess
dispatcher path for isolation.

The persistent path still creates a fresh Codex thread per request. This avoids
cross-request context contamination while testing whether app-server process
reuse is enough to improve latency.

Translation helper requests now opt into a narrower experiment:

- reuse one helper Codex thread per worker/model/prompt profile;
- send the compact translation task directly instead of wrapping it in the full
  worker role configuration prompt.
- use the dedicated helper model `gpt-5.4-mini` regardless of the selected
  visual card LLM, so helper-thread reuse is not fragmented by workflow content
  settings.

Mini-chat and broader dispatcher workflows still use fresh request context.

Visual-agent mini-chat now uses a dedicated persistent path instead of the
dispatcher worker wrapper:

- one Codex thread is cached per visual card/profile hash;
- card work-package fields are sent as thread developer instructions;
- each mini-chat user message is sent as a normal turn in that thread;
- opening the mini-chat can warm the thread through `/api/agents/chat-warmup`.

Live smoke on 2026-06-18 showed:

- cold visual-agent first send without warmup: 14.19 seconds;
- second send in the same thread: 2.35 seconds;
- thread-only warmup: 5.28 seconds, followed by a first send of 7.30 seconds
  because MCP/turn activation still starts on the first real turn;
- hidden priming turn after warmup: 9.13 seconds, followed by a real send of
  2.76 seconds.

Therefore, persistent threads remove repeated `codex_thread_started` cost, but
fully Codex-like first-message latency requires a product decision about hidden
priming turns or a lower-level way to pre-initialize MCP/turn activation without
adding conversation state.

Initial live smoke result:

- First translation in a fresh manager: 12.87 seconds.
- Second translation in the same manager with helper-thread reuse: 1.37 seconds.
- Timing logs showed the removed cost directly: thread reuse avoided the
  roughly 5.15 second `codex_thread_started` step, and compact follow-up turn
  completed in roughly 1.36 seconds.

## Worker Debug Visibility

Speed remains the priority for real planner/executor/reviewer runs. Worker
sessions may still appear in the Codex sidebar because the dispatcher uses
Codex app-server instead of a fully hidden runtime. The mini-orchestrator UI
therefore treats those sessions as visible technical artifacts rather than
trying to hide them in this increment.

For dispatcher plan previews and approved runs, the UI response includes a
compact `tech` summary built from the generated JSONL log. The dashboard shows
that summary in a separate **Tech** tab with runtime, log path, dispatch
decision, worker thread/turn ids, timing events, event counts, Codex
notification counts, and recent compact events. The summary intentionally
stores prompt/output lengths instead of duplicating full prompt and model text;
the log path remains the source for deeper replay.

Worker chats are routed to a separate technical workspace through
`tools/project-memory/service-runtime.json` `workerChatRoot`, currently
`D:/AI/orchestrator-worker-chats`. Codex app-server starts from that folder and
creates threads with that cwd so Codex sidebar grouping should move worker chats
out of the `mini-orchestrator` project. Worker turns still receive the real
mini-orchestrator path as `cwd` and `runtimeWorkspaceRoots` so executor/reviewer
work remains targeted at the project. The `Tech` tab and JSONL events show both
`workerChatRoot` and `targetWorkspace`.
