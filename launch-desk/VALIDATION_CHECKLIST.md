# Launch Desk Validation Checklist

Use this checklist before considering a release candidate complete.

## Local run checks

- [ ] `OPENAI_API_KEY` is present in environment or `.env`.
- [ ] Backend starts with `npm run dev:backend`.
- [ ] Frontend starts with `npm run dev:frontend`.
- [ ] `GET /api/health` returns status `ok`.
- [ ] Backend route `POST /api/plan` returns SSE headers (`text/event-stream`).

## Streaming checks

- [ ] Response emits at least one `tool_progress` event.
- [ ] Response emits at least one `model_delta` event.
- [ ] `final` event contains `finalOutput` text and event flags.
- [ ] Final output includes:
  - Prioritized plan
  - Risk register
  - Owner checklist
  - Launch copy
  - Follow-up questions (if key fields are missing)

## Tool coverage checks

- [ ] Extract tasks tool is executed and returns structured task buckets.
- [ ] Readiness tool returns score + blocking gaps.
- [ ] Owner checklist tool returns grouped owners.
- [ ] Channel copy tool returns at least 3 channel drafts.
- [ ] Follow-up question tool runs when inputs are incomplete.

## Security/compliance checks

- [ ] No hard-coded secrets in source files.
- [ ] `.env.example` is documented and copied locally.
- [ ] No unrelated files modified.

## UX checks

- [ ] Frontend is responsive (desktop + mobile).
- [ ] User can see live tool progress and model output as stream events arrive.
- [ ] Final cards are rendered from the final assistant output.
