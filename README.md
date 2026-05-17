# Auto Slack Avatar

Generates a square profile image with **Google Gemini** (`GEMINI_IMAGE_MODEL`,
default `gemini-2.5-flash-image`) from a random base photo and prompts for
**today’s weekday** (see `prompts.json`). The Gemini reply is converted to
PNG; before Slack upload the image is **center-cropped to a square**, resized
to **1024×1024**, and saved under `output/` with a timestamped filename, then
**`users.setPhoto`** is called.

## Requirements

- Python **3.12**
- Slack **user token** (`xoxp-…`) with **`users.profile:write`**
- **Gemini API key** from [Google AI Studio](https://aistudio.google.com/)

### Slack app (one-time)

1. Create an app at [api.slack.com/apps](https://api.slack.com/apps).
2. **OAuth & Permissions** → **User Token Scopes** → add `users.profile:write`.
3. Install the app to your workspace and copy the **User OAuth Token**.

## Setup (virtual environment)

```bash
cd auto-slack-avatar
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
# Edit .env with real tokens and TZ
```

Use your clone directory if the folder name differs.

Put source photos in **`assets/images/`** (`.png`, `.jpg`, `.jpeg`, `.webp`, `.heic`, `.heif`).
Only files **directly inside** that folder are used (no subfolders).

Edit **`prompts.json`**: a single **JSON object** with **no extra keys**. Required:

- **`base_prompt`**: string (non-empty). Shared instructions for every run (Slack
  avatar constraints, style rules, etc.).
- **`monday` … `sunday`**: each value is a **JSON array of strings**; each day
  must have **at least one** non-empty string after trimming.

The text sent to Gemini is **`base_prompt`**, a blank line, then the chosen
weekday string (`base` + day-specific stylistic prompt).

Gemini may return image bytes in the model’s format; the code **opens the result
with Pillow and saves PNG (RGBA)** before the Slack resize step.

### Randomness

The process uses **`random.seed`**:

1. If **`RUN_SEED`** is set in `.env` (integer), that value is used.
2. Otherwise **`run_seed = int(time.time())`** at startup.

Order after seeding: resolve weekday from **`TZ`** → `random.choice` on that
day’s prompt list → `random.choice` on the image file list. The seed is logged
so you can replay picks for debugging.

### Output files

Processed PNGs are written to **`output/`** as:

`avatar_YYYY-MM-DD_HHMMSS.png` using the **local time in `TZ`** (e.g.
`avatar_2026-05-16_143052.png`).

## Run locally

From the project root (with venv activated):

```bash
python -m src.run_daily
```

## Docker Compose (one-shot)

No cron inside the container; run when you want an update:

```bash
docker compose run --rm avatar-job
```

Ensure `.env` exists and mount paths in `docker-compose.yml` match your machine.

### Environment variables

| Variable | Description |
|----------|-------------|
| `SLACK_USER_TOKEN` | User OAuth token (`xoxp-…`). |
| `GEMINI_API_KEY` | Gemini Developer API key. |
| `GEMINI_IMAGE_MODEL` | Model id (default `gemini-2.5-flash-image`). |
| `TZ` | IANA zone, e.g. `America/Santiago`. |
| `RUN_SEED` | Optional integer to fix random choices. |
| `STRICT_GEMINI` | If `1` / `true` / `yes` / `on`, the run **fails** when Gemini hits quota or certain rate limits. If unset (default), some **429 / exhausted quota** cases fall back to uploading the **raw base photo** (no AI edit). See `.env.example`. |
| `ASSETS_DIR` | Default `assets/images`. |
| `PROMPTS_PATH` | Default `prompts.json`. |
| `OUTPUT_DIR` | Default `output`. |

## Lint / format (PEP8 via Ruff)

```bash
ruff check src
ruff format src
```

## Scheduling (later)

Use an external scheduler (Cloud Scheduler, GitHub Actions `schedule`, host
cron, etc.) to invoke the same command or `docker compose run` on your cadence.

## Troubleshooting

- **`missing_scope` / `invalid_auth`**: check the user token and reinstall the
  app if scopes changed.
- **Gemini returns no image**: model or region may not support image output;
  try another `GEMINI_IMAGE_MODEL` from the current AI Studio docs.
- **Quota / 429**: with default settings the job may upload your **original**
  base file if Gemini refuses; set **`STRICT_GEMINI=1`** to fail the run instead.
- **`prompts.json` errors**: unknown keys, missing `base_prompt`, or empty weekday
  lists are rejected at startup.
- **Slack `bad_image`**: rare if the post-process step ran; the code expects a
  decodable raster and outputs **1024×1024** square PNG for Slack.
# Auto-Slack-Avatar
