# Handoff Summary: Codex, ChatGPT, Symphony, and current project mapping

Date: 2026-06-18 14:46:07
Thread topic: Explain how Codex works with ChatGPT, study OpenAI Symphony, and prepare the project context for a possible Symphony-style integration.

## User Intent

- The user is not only asking for a general explanation of Symphony.
- The user wants to understand whether and how Symphony can be integrated into
  this mini-orchestrator project.
- Treat future Symphony-related work as an integration/design task:
  - compare Symphony's architecture with the current project;
  - identify which Symphony concepts should be adopted;
  - avoid blindly copying the whole repository if a smaller local control plane
    is enough;
  - preserve the current visual-agent UI, mini-chat, translator, and dispatcher
    behavior while adding task/run orchestration.

## Current Repo State

- Current workspace: `D:\AI\mini-orchestrator`.
- Branch after the last push: `main`.
- Remote tracking branch: `origin/main`.
- Last committed and pushed work:
  - Commit: `efdf707 Add persistent Codex visual agent runtime`.
  - Push result: `main -> origin/main`.
- Checks run before that push:
  - `python -m pytest tests\test_agent_api.py`
    - Result: 9 passed.
  - `python -m compileall mini_orchestrator tools\codex-dispatcher`
    - Result: no errors.
- `git status --short --branch` during this summary command showed:
  - `## main...origin/main`
  - No tracked or untracked changes printed before this summary file was added.

## Recently Completed Work

- Persistent visual-agent mini-chat runtime was implemented and pushed.
- Mini-chat now maps closely to a real Codex conversation:
  - UI `/agents-builder`
  - `/api/agents/chat`
  - `VisualAgentApi`
  - `PersistentCodexDispatcher`
  - Codex `app-server`
  - persistent Codex thread per selected visual-agent card/profile
  - `turn/start`
  - mini-chat response in the UI.
- Mini-chat no longer routes every message through a cold planner-style
  dispatcher task.
- Mini-chat work-package data is sent as thread developer instructions.
- `/api/agents/chat-warmup` exists to prepare a persistent Codex thread when a
  mini-chat opens.
- Work-package translation is separated from agent-card behavior:
  - Translation goes through a dedicated helper path.
  - Translation uses helper model `gpt-5.4-mini`.
  - Translation does not use the selected card model.

## User Questions Answered

- Explained in detail how Codex works with ChatGPT/OpenAI from user text entry
  to final answer:
  - client/app gathers project context, instructions, tools, sandbox, and chat
    history;
  - starts or resumes a thread;
  - sends a turn to OpenAI/Codex backend;
  - model internally reasons;
  - raw chain-of-thought is not exposed;
  - user can see status, reasoning summaries, tool events, partial assistant
    output, and final response;
  - tool calls execute locally under the runtime's permission/sandbox model;
  - the model loops through observations until it returns a final message.
- Clarified the difference between ChatGPT account authorization for Codex
  app-server and direct OpenAI API usage:
  - Codex app-server can use the signed-in ChatGPT/Codex authorization path.
  - Direct OpenAI API work still needs API credentials such as `OPENAI_API_KEY`
    when the app itself calls the API.
- Confirmed how our current mini-chat and translator work:
  - Mini-chat is close to the Codex persistent-thread model.
  - Translator is a UI helper, not the selected visual agent itself.

## Symphony Findings

- Reviewed OpenAI's `openai/symphony` project and the official Russian OpenAI
  article about open-source Codex orchestration with Symphony.
- Main conclusion:
  - Symphony is a long-running orchestrator daemon and task-control plane for
    Codex agents, not a mini-chat UI.
- Symphony should be understood as an orchestration/control-plane pattern:
  - a background process owns task selection, claim/run state, retries,
    continuation, and human-review handoff;
  - Codex remains the agent runtime that performs the actual reasoning and
    coding work;
  - the task tracker or project queue becomes the source of truth for work
    state.
- Symphony flow:
  - task tracker such as Linear;
  - Symphony daemon polling/claiming eligible tasks;
  - per-task workspace creation;
  - workflow prompt/config from repo policy such as `WORKFLOW.md`;
  - Codex app-server thread/turn execution;
  - status, retry, continuation, blocked, review, and done states.
- Key architectural idea:
  - Manage tasks and outcomes, not individual chat sessions or PRs.
- Useful concepts for this project:
  - task/ticket as the primary orchestration object;
  - daemon or controller loop separate from the interactive mini-chat UI;
  - versioned workflow contract such as `WORKFLOW.md` or
    `ORCHESTRATOR_WORKFLOW.md`;
  - explicit lifecycle states: `queued`, `claimed`, `running`, `blocked`,
    `needs_review`, `failed`, `done`;
  - distinction between "Codex turn completed" and "task actually done";
  - per-task workspaces/run contexts for serious work;
  - structured event/timing logs and continuation turns;
  - controlled follow-up task creation by agents.

## Symphony Integration Notes

- Do not treat Symphony as a replacement for the current UI.
- The current project can integrate Symphony-style orchestration underneath or
  beside the visual builder:
  - visual builder defines agents, chains, work packages, and user-facing
    configuration;
  - a Symphony-inspired controller can claim queued tasks/runs and execute them
    through the dispatcher/Codex app-server path;
  - mini-chat remains an interactive test surface for a selected visual agent;
  - translator remains a UI helper, not a workflow agent.
- The natural local integration shape is likely:
  - `Workflow Contract`:
    - `AGENTS.md`, project-memory specs, and a future `WORKFLOW.md` or
      `ORCHESTRATOR_WORKFLOW.md`;
  - `Run Queue / Task Store`:
    - local queued work items created from UI, chat command, or task-manager
      integration;
  - `Lifecycle Controller`:
    - moves work through `queued`, `claimed`, `running`, `blocked`,
      `needs_review`, `failed`, and `done`;
  - `Execution Layer`:
    - current `PersistentCodexDispatcher`, dispatcher chain, and Codex
      app-server integration;
  - `Status Surface`:
    - UI/API endpoints showing current run state, logs, review needs, and
      final result.
- Integration should start with a small local contract and lifecycle model
  before adding a full background daemon or external task tracker.
- The project should keep a strict distinction between:
  - a Codex turn returning successfully;
  - a dispatcher role completing;
  - the whole task being accepted as done;
  - the human approving or merging the result.
- Serious tasks should eventually use isolated run context/workspace metadata
  rather than sharing only one UI thread.

## Project Mapping

- Current project already has:
  - visual workflow builder UI;
  - agent cards and mini-chat;
  - translation helper;
  - dispatcher chain;
  - Codex app-server integration;
  - persistent visual-agent thread support.
- Architecture is already moving in a similar direction to Symphony:
  - `PersistentCodexDispatcher` acts as a small piece of the execution layer.
  - `tools/project-memory/*` and `AGENTS.md` partially act as the workflow
    contract.
  - The current dispatcher chain is an early form of an orchestrator/agent
    runner.
- The main missing layer is not "more chat"; it is an explicit task/run control
  plane that can own state, retries, review, and completion.
- Current project does not yet fully have Symphony-style:
  - daemon polling a task tracker;
  - task claiming and lease/retry lifecycle;
  - per-issue workspace manager;
  - versioned workflow policy file used as launch contract;
  - full task-state reconciliation surface.

## Suggested Next Implementation Direction

- Phase 1: write the local workflow contract.
  - Add a project-local workflow contract file:
  - candidate name: `ORCHESTRATOR_WORKFLOW.md` or `WORKFLOW.md`.
  - Define what counts as plan, execute, validate, review, blocked, and done.
- Phase 2: add or formalize run lifecycle states separate from chat completion.
- Phase 3: record task/run events in a structured way that can support retries,
  continuation, review, and status surfaces.
- Phase 4: connect the lifecycle controller to the existing dispatcher/Codex
  app-server execution path.
- Phase 5: consider a small Symphony-inspired local daemon only after the
  workflow contract and lifecycle states are clear.

## Sources Consulted

- Official OpenAI Codex docs and help pages for the Codex/ChatGPT explanation.
- GitHub repository: `https://github.com/openai/symphony`.
- Symphony specification in the repository.
- Official OpenAI article:
  `https://openai.com/ru-RU/index/open-source-codex-orchestration-symphony/`.

## Continuation Point

- If the user asks to implement the Symphony-inspired direction, first inspect:
  - current `git status --short --branch`;
  - `mini_orchestrator/agent_api.py`;
  - `mini_orchestrator/codex_dispatcher_service.py`;
  - `tools/codex-dispatcher/`;
  - `tools/project-memory/agent-flow-builder.md`;
  - `tools/project-memory/dispatcher-codex-optimization.md`;
  - `tools/project-memory/pending-tasks.md`.
- For non-trivial architecture changes, update durable project memory in the
  same scoped change.
- Keep normal work inside `D:\AI\mini-orchestrator`.
