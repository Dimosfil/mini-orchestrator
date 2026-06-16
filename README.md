# Mini Orchestrator + Campaign Concept Studio

Mini Orchestrator now includes a **full-stack campaign concept studio** UI at `/`:

- enter campaign brief, target audience, product details, tone, and channels
- generate:
  - concise campaign concept
  - 3 headline/body copy variants
  - launch checklist
  - image prompts
  - generated campaign visuals (base64 images from OpenAI image generation tool)

## Install

```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1
python -m pip install -e .
```

## Run

```powershell
python -m mini_orchestrator --ui
```

Optional flags:

- `--host` (default `127.0.0.1`)
- `--port` (default `8765`)
- `--open-browser`

Then open `http://127.0.0.1:8765`.

## Example flow

Open the web UI and fill the form like this:

```text
Campaign brief:
Launch a lightweight AI planning tool for small marketing teams that need faster campaign ideas.

Target audience:
Marketing managers and founders at small B2B SaaS companies.

Product details:
A browser-based studio that turns a rough brief into campaign concepts, copy variants,
launch checklists, visual prompts, and generated campaign direction images.

Tone:
Friendly

Channels:
Instagram, Meta Ads, Email, Landing page
```

After you click **Generate campaign**, the app returns:

- a short campaign concept
- three headline/body copy directions
- a practical launch checklist
- image prompts for the creative direction
- generated campaign images rendered directly in the browser

The result is meant as a first creative draft for a marketing team, not a final approved campaign.

## API key and environment

- `OPENAI_API_KEY` (required for campaign generation)
- `MINI_ORCHESTRATOR_OPENAI_API_KEY_ENV` (optional override, default `OPENAI_API_KEY`)
- `MINI_ORCHESTRATOR_OPENAI_BASE_URL` (optional OpenAI-compatible base URL)

Campaign model/prompt/image knobs:

- `MINI_ORCHESTRATOR_CAMPAIGN_TEXT_MODEL` (default `gpt-5.5`)
- `MINI_ORCHESTRATOR_CAMPAIGN_IMAGE_MODEL` (default `gpt-image-2`)
- `MINI_ORCHESTRATOR_CAMPAIGN_IMAGE_SIZE` (default `1024x1024`)
- `MINI_ORCHESTRATOR_CAMPAIGN_IMAGE_QUALITY` (default `medium`)
- `MINI_ORCHESTRATOR_CAMPAIGN_IMAGE_COUNT` (default `3`)

For quick prompt/model tuning without touching frontend code, edit:

- text + JSON schema + campaign prompt in `mini_orchestrator/llm.py`
  (`OpenAiResponsesClient.generate_campaign` and schema definition)
- image tool settings inside the same method (`tools` and `tool_choice`)

## API endpoints

Existing endpoint remains:

- `POST /api/run` — orchestrator JSON workflow run

New endpoint for studio:

- `POST /api/campaign` — accepts JSON body:

```json
{
  "brief": "...",
  "target_audience": "...",
  "product_details": "...",
  "tone": "...",
  "channels": ["Instagram", "Meta Ads"]
}
```

The response contains campaign content and generated images under `generated_images`.

## Client/server boundary (important)

- All OpenAI requests stay on the server.
- The browser UI sends user inputs only to `/api/campaign`.
- The server calls the OpenAI Responses API and returns only JSON response artifacts.

This keeps API keys off the client and allows you to rotate keys server-side.

## Validation plan (small)

Run after first deploy:

1. Open UI, fill valid fields, click **Generate campaign**.
2. Verify you see:
   - concept text
   - exactly 3 headline/body variants
   - non-empty checklist
   - 3 image prompts and matching images.
3. Confirm error states:
   - empty input fields show user-facing validation errors
   - missing `OPENAI_API_KEY` returns a 502-like message from the boundary.
4. Check model and image settings by temporarily setting:
   - `MINI_ORCHESTRATOR_CAMPAIGN_TEXT_MODEL`
   - `MINI_ORCHESTRATOR_CAMPAIGN_IMAGE_MODEL`
5. Optional: test with fallback channels and short prompt to ensure schema parsing still returns valid JSON.

## Deploy notes

- App is a single Python package; deploy as a long-running process (systemd, Docker, or host process manager).
- Keep `.venv`, API keys, and logs out of VCS.
- For Docker, expose port `8765` and provide env vars above at runtime.
- Ensure outbound HTTPS access to OpenAI APIs for both:
  - `https://api.openai.com/v1/responses`
  - response-based image generation workflow in the same endpoint.
- Keep this repo as the source of truth and pin runtime versions used in deployment.
