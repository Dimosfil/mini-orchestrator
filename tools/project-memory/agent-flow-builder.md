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
  - `workPackage`
  - `x`
  - `y`
- Built-in presets are `planner`, `executor`, `reviewer`, `agent`, and
  `custom`. A preset defines the default role, name prefix, model, speed,
  reasoning level, and initial work-package text.
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
  `localStorage`; translations are UI guidance only and are not persisted into
  the agent flow JSON. Built-in preset text uses local dictionary translations,
  while user-edited text can show an explicit unavailable-translation notice.
- Work-package fields are prompt text. They are stored with the visual card and
  should be passed to future orchestrator execution as a structured handoff
  package instead of forwarding the whole mini-chat history.
- The flow model may also store `presetSettings`, a browser-local set of
  user-edited preset defaults used when creating new cards from the sidebar.
- Supported MVP `llm` values include `gpt-5.5`, `gpt-5.4`,
  `gpt-5.4-mini`, `gpt-5.3-codex-spark`, `gpt-5`, `gpt-4.1-mini`,
  and `rules`. The default is `gpt-5.5`.
- Stored agent cards with an unsupported `llm` value are normalized to the
  default on load so stale browser-local flows do not keep calling unsupported
  models.
- Supported MVP `speed` values are `fast`, `balanced`, and `careful`.
- Supported MVP `reasoning` values are `low`, `medium`, `high`, and
  `very_high`.
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

Validation should check:

- all connection endpoints refer to existing agents;
- each connection starts at a supported output port (`success` or `failure`)
  and ends at an input port;
- at least one start agent is identifiable;
- cycles are rejected unless the flow explicitly supports loop semantics;
- every agent has a supported LLM, speed, and reasoning value.

Execution should translate the visual graph into the existing
plan -> execute -> validate lifecycle only after validation succeeds.

## Implementation Map

- Backend static route: `mini_orchestrator/ui.py`
- Main UI entry button: `mini_orchestrator/web/index.html`
- Builder MVP page: `mini_orchestrator/web/agents-builder.html`
