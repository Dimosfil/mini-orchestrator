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
- Users can add agent cards from role presets: `Planner`, `Executor`,
  `Reviewer`.
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
  `gpt-5.4-mini`, `gpt-5.3-codex-spark`, `gpt-5-mini`, `gpt-5`,
  `gpt-4.1-mini`, and `rules`.
- Supported MVP `speed` values are `fast`, `balanced`, and `careful`.
- Supported MVP `reasoning` values are `low`, `medium`, `high`, and
  `very_high`.
- Cards can be moved within the workspace and persist their positions.
- Cards expose an input port and an output port.
- Dragging from an output port to another card input port creates a directed
  connection.
- Connections are rendered as flexible SVG arrows and update when cards move.
- The browser stores the flow in `localStorage` under
  `mini-orchestrator-agent-flow-v1`.

## Flow Model

```json
{
  "agents": [
    {
      "id": "agent-...",
      "name": "Planner 1",
      "role": "Planner",
      "llm": "gpt-5-mini",
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
      "fromPort": "output",
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
- each connection starts at an output port and ends at an input port;
- at least one start agent is identifiable;
- cycles are rejected unless the flow explicitly supports loop semantics;
- every agent has a supported LLM, speed, and reasoning value.

Execution should translate the visual graph into the existing
plan -> execute -> validate lifecycle only after validation succeeds.

## Implementation Map

- Backend static route: `mini_orchestrator/ui.py`
- Main UI entry button: `mini_orchestrator/web/index.html`
- Builder MVP page: `mini_orchestrator/web/agents-builder.html`
