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
- Users add agent cards through a single `Добавить агента` action. New cards
  start with local defaults and can be renamed/configured on the card.
- Each agent card stores:
  - `id`
  - `name`
  - `role`
  - `llm`
  - `speed`
  - `reasoning`
  - `x`
  - `y`
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
      "role": "Planner",
      "llm": "gpt-5.5",
      "speed": "fast",
      "reasoning": "medium",
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
