# Agent Flow Builder

## Purpose

The agent flow builder is a visual workspace for configuring agent workflows
before they are saved, validated, or executed by mini-orchestrator.

The current MVP is browser-local. It must not imply that a flow is executable
until a backend save/validate/run contract is implemented.

## MVP Behavior

- The main Web UI exposes a `Настройка агентов` button.
- The button opens `/agents-builder` in a separate browser window or tab.
- The builder has a left control panel and a central flow workspace.
- Users add agent cards by choosing a preset from the sidebar dropdown and
  clicking `Добавить агента`. Presets are editable starting templates, not
  fixed worker types.
- The sidebar shows a compact preview for the selected preset between the
  preset dropdown and `Добавить агента`. The preview includes role, runtime
  settings, name prefix, a short work-package summary, and a settings button.
- Editing a preset from the preview opens the same settings dialog used by
  cards. Changes are staged in the dialog and apply only after `Сохранить`;
  `Отмена` or closing the dialog discards the draft.
- Each agent card stores:
  - `id`
  - `name`
  - `preset`
  - `role`
  - `llm`
  - `speed`
  - `reasoning`
  - `accessMode`
  - `workPackage`
  - `x`
  - `y`
- Built-in presets are `planner`, `executor`, `reviewer`, `agent`, and
  `custom`. A preset defines the default role, name prefix, model, speed,
  reasoning level, access mode, and initial work-package text.
- Each card has an agent settings dialog. The dialog exposes runtime settings
  and the work-package prompt fields:
  - `role/instructions`
  - `current objective`
  - `inputs/artifacts`
  - `constraints`
  - `previous agent outputs`
  - `allowed tools/actions`
  - `expected output format`
- The work-package editor shows a read-only translation next to each prompt
  field. The selected translation language is stored separately in browser
  `localStorage`; translations are UI guidance only and must not be sent as
  executable prompt fields. Built-in preset text uses local dictionary
  translations.
  Edited prompt text updates the settings draft while typing, but the visible
  translation refreshes only after the textarea loses focus so typing is not
  interrupted by immediate helper-text changes. If a changed text has no local
  dictionary translation, the builder calls `/api/agents/translate-work-package`
  after blur and replaces the helper text with the agent-generated translation
  when it returns. Saving settings persists the edited work-package text and
  its generated translation together under `workPackageTranslations`, so the
  new text/translation pair becomes the current UI helper state.
- Work-package translation is latency-sensitive UI helper behavior, but the
  active LLM channel is the dispatcher/Codex-agent path. Direct OpenAI Responses
  API translation and API-key provisioning are deferred and must not be the
  default runtime path until that decision is reopened.
- Work-package translation uses an application-owned helper model, currently
  `gpt-5.4-mini`, and must not inherit the selected `llm` value from an agent
  card. A card's `llm` is content/runtime configuration for the workflow being
  designed; the translator is UI infrastructure owned by the builder.
- Reviewer runtime settings are separate from the translation helper. Reviewer
  execution must use the `llm` stored on the selected chain preset/card. The
  dispatcher must not silently replace a preset/card reviewer model with a role
  fallback.
- Work-package fields are prompt text. They are stored with the visual card and
  should be passed to future orchestrator execution as a structured handoff
  package instead of forwarding the whole mini-chat history.
- The flow model may also store `presetSettings`, a browser-local set of
  user-edited preset defaults used when creating new cards from the sidebar.
- Agent chains are selectable presets. The builder has a chain preset dropdown
  with a default `planner -> executor -> reviewer` chain. Saving the current
  visible cards and connections asks for a chain name, stores the chain as a
  browser-local preset, and adds it to the dropdown. Loading a chain preset
  replaces the visible canvas with that preset's agents and connections. This
  keeps a chain as a reusable workflow preset, while individual cards remain
  editable inside the selected chain.
- When saving while a user-created chain preset is selected or currently loaded,
  the builder must ask whether to overwrite that preset or save the canvas as a
  new preset. Overwrite keeps the selected preset id so the user can edit the
  current chain instead of accidentally creating duplicates or silently
  replacing data.
- The executable dashboard also has an `Исполнительная цепочка` dropdown backed
  by the same browser-local chain presets. When the user starts an approved
  workflow, the selected chain preset is sent with the run request and recorded
  in the dispatcher JSONL log as `chain_selected`. The dashboard must send the
  full agent runtime settings, including `llm`, `reasoning`, `accessMode`, and
  `workPackage`; it must not reduce agents to display-only `id/name/role`
  metadata.
- Approved dispatcher workflows write the selected preset to SQLite table
  `dispatcher_chain_presets` in `.mini_orchestrator/runtime.sqlite3` and pass
  the run id to `tools/codex-dispatcher/dispatcher.py --chain-preset-id`.
  The dispatcher compiles those agents into in-memory worker profile
  instructions, orders workers by the chain graph, and launches Codex
  app-server turns with each agent's selected model, reasoning, access mode,
  and work package. Executable chain presets must carry each agent's selected
  `llm`; missing model settings are validation errors, not a reason to apply
  role defaults.
- Live Runs then shows one task card in `In Progress`, the current worker as
  `Current`, and the selected chain's agents as stage chips inside that task
  card.
- Supported MVP `llm` values include `gpt-5.5`, `gpt-5.4`,
  `gpt-5.4-mini`, `gpt-5.3-codex-spark`, `gpt-5`, `gpt-4.1-mini`,
  and `rules`. The default is `gpt-5.5`.
- Stored agent cards with an unsupported `llm` value are normalized to the
  default on load so stale browser-local flows do not keep calling unsupported
  models.
- Supported MVP `speed` values are `fast`, `balanced`, and `careful`.
- Supported MVP `reasoning` values are `low`, `medium`, `high`, and
  `very_high`.
- Supported MVP `accessMode` values are `danger-full-access`,
  `workspace-write`, and `read-only`. The temporary default is
  `danger-full-access` so real file-writing Codex app-server workflow tests do
  not stop at the file-change approval gate. The card UI must keep this visible
  because full access removes sandbox boundaries.
- Cards can be moved within the workspace and persist their positions.
- Cards can be deleted with the mini `×` button in the card header or with the
  `Delete` key when the card is selected and focus is not inside a text field
  or select control. Deleting a card also removes all incoming and outgoing
  connections for that card.
- Cards expose one input port and two output ports: `success` (`успех`) and
  `failure` (`не успех`), matching flowchart-style branching.
- Dragging from either output port to another card input port creates a
  directed connection for that outcome branch.
- Connections are rendered as flexible SVG arrows and update when cards move.
- Clicking a connection selects it for editing. The selected connection can be
  reattached to another source/target agent, switched between the `success` and
  `failure` outgoing branches, or deleted.
- Pressing `Delete` removes the currently selected connection when focus is not
  inside a text field or select control.
- When several connections enter the same agent, their input endpoints are
  vertically offset and numbered so the separate incoming arrows remain visible.
  Clicking the numbered badge selects that connection for reattaching.
- The browser stores the flow in `localStorage` under
  `mini-orchestrator-agent-flow-v1` only when the user clicks `Сохранить`.
  Save rebuilds the JSON model from the currently visible agent cards and
  connections.
- The sidebar shows a readable flow summary plus compact JSON preview instead
  of using a raw editable JSON textarea as the primary display.
- Each card has a collapsed mini-chat button. Opening it reveals a message
  window, text input, and send button for checking the selected agent style.
  The mini chat calls `/api/agents/chat` only for live LLM models; `rules` cards
  show a local fallback notice. Empty dispatcher output is an error and must be
  shown in the mini chat instead of rendering a blank assistant message.
- The builder topbar is save/reset only. It is a constructor for agent cards and
  chain presets, not a task execution surface. Running a task from the builder
  is intentionally not user-facing; execution belongs in the main
  dashboard/Kanban workflow where the user selects the chain preset that should
  run the task.
- When saved flow execution is added, Live Runs must represent the configured
  agent chain as one task card in `In Progress`. The card should show the
  current working visual card/agent as `currentAgent` and render the configured
  stage chain inside the task card. Individual agents should not become
  separate Kanban task cards for the same user task.
- Mini-chat is a real visual-agent runtime check, not a lightweight helper. The
  UI path keeps one persistent Codex thread per card/profile hash, puts the
  card's work-package fields into thread developer instructions, and sends
  ordinary user messages as turns in that thread. It must not route each
  mini-chat message through a cold `orchestrator planner` dispatcher wrapper.
  The profile hash includes `accessMode`, so changing card access creates a new
  Codex thread with matching app-server sandbox/approval settings.
  Opening a mini-chat may call `/api/agents/chat-warmup` to create the thread
  before the first message; full priming turns are a separate latency trade-off
  because they add hidden conversation state and can make immediate sends wait
  longer.
- Mini-chat tasks with non-ASCII text are passed to the dispatcher through a
  UTF-8 task file, and dispatcher JSON responses are written to stdout as UTF-8
  bytes. This preserves Cyrillic user messages and agent responses on Windows.

## Flow Model

```json
{
  "agents": [
    {
      "id": "agent-...",
      "name": "Planner 1",
      "preset": "planner",
      "role": "Planner",
      "llm": "gpt-5.5",
      "speed": "fast",
      "reasoning": "medium",
      "workPackage": {
        "instructions": "Turn rough user intent into a scoped plan...",
        "currentObjective": "Clarify what should be built...",
        "inputsArtifacts": "User request, selected workflow...",
        "constraints": "Do not edit files during planning.",
        "previousOutputs": "Use prior coordinator summaries only when current.",
        "allowedTools": "Read-only inspection and planning.",
        "expectedOutput": "Objective, steps, risks, handoff, checklist."
      },
      "workPackageTranslations": {
        "ru": {
          "instructions": "Перевод текущего текста role/instructions."
        }
      },
      "x": 360,
      "y": 90
    }
  ],
  "connections": [
    {
      "id": "connection-...",
      "fromAgentId": "agent-...",
      "toAgentId": "agent-...",
      "fromPort": "success",
      "toPort": "input"
    }
  ],
  "nextAgentNumber": 2
}
```

## Future Backend Contract

Future backend integration should add explicit endpoints instead of treating the
localStorage model as executable state:

- `GET /api/agent-flows`
- `POST /api/agent-flows`
- `GET /api/agent-flows/{id}`
- `PUT /api/agent-flows/{id}`
- `POST /api/agent-flows/{id}/validate`
- `POST /api/agent-flows/{id}/run`
- `POST /api/agents/translate-work-package`

Validation should check:

- all connection endpoints refer to existing agents;
- each connection starts at a supported output port (`success` or `failure`)
  and ends at an input port;
- at least one start agent is identifiable;
- the primary `success` path is acyclic unless a cycle includes a PM control
  card, while `failure` edges may define bounded rework loops such as
  QA -> executor;
- every agent has a supported LLM, speed, and reasoning value.

Execution should translate the visual graph into the configured agent chain
preset and only fall back to the default plan -> execute -> validate lifecycle
when no explicit executable preset is supplied.

## Implementation Map

- Backend static route: `mini_orchestrator/ui.py`
- Visual agent chat API behavior: `mini_orchestrator/agent_api.py`
- Persistent Codex app-server and visual-agent mini-chat runtime:
  `mini_orchestrator/codex_dispatcher_service.py`
- Main UI entry button: `mini_orchestrator/web/index.html`
- Builder MVP page: `mini_orchestrator/web/agents-builder.html`
