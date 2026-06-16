# Launch Desk

Launch Desk is a polished web app that helps engineering teams convert a rough launch idea into:

- A prioritized release plan
- A risk register with mitigation
- A role-based owner checklist
- Channel-specific launch copy
- Targeted follow-up questions when required details are missing

The app uses the current OpenAI Agents SDK on the backend and streams progressive updates (tool progress + model text delta) to the browser.

## Project structure

- `launch-desk/backend`: Express API and OpenAI Agents setup
  - `src/agent`: agent prompt, tools, schemas, and utility helpers
  - `src/routes`: streaming endpoint implementation
  - `tests`: lightweight tool tests
- `launch-desk/frontend`: React + Vite UI with SSE client parser and live output cards
- `.env.example`: environment variable template

## Prerequisites

- Node.js 22+ (tested on Node 24)
- `OPENAI_API_KEY` available in the environment or `.env`

## Setup

```powershell
cd launch-desk
copy .env.example .env
# Fill in OPENAI_API_KEY and any optional settings
npm run install:all
```

## Run backend + frontend

From `launch-desk` root:

```powershell
npm run dev
```

Expected local URLs:

- Backend: `http://localhost:4000`
- Frontend: `http://localhost:5173`

## API contract

`POST /api/plan` (JSON body):

- `brief`: string
- `audience`: string
- `launchDate`: string
- `constraints`: string
- `assets`: array of strings

Response is Server-Sent Events (SSE). The frontend listens for:

- `tool_progress` events
- `model_delta` events
- `final` event with full output
- `done` event

## Model and tracing

- Default model: `gpt-5.4-mini` unless `LAUNCH_DESK_MODEL` or `OPENAI_DEFAULT_MODEL` is set.
- Tracing uses Agents SDK options:
  - `workflowName`
  - `groupId`
  - `traceMetadata`
  - `tracingDisabled`
  - optional `OPENAI_API_TRACING_KEY` for custom trace provider key

## Testing

Backend tool tests:

```powershell
cd launch-desk/backend
npm run test
```

## Helpful docs

- OpenAI Agents SDK quickstart and streaming reference: https://openai.github.io/openai-agents-js/
- Models overview: https://developers.openai.com/api/docs/models
