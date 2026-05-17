# Auto Slack Avatar

Generates a square profile image with **Google Gemini** (`GEMINI_IMAGE_MODEL`,
default `gemini-2.5-flash-image`) from a random base photo and prompts for
**today’s weekday** (see `prompts.json`). The Gemini reply is converted to
PNG; before Slack upload the image is **center-cropped to a square**, resized
to **1024×1024**, and saved under `output/` with a timestamped filename, then
**`users.setPhoto`** is called.

Optional Slack **job titles** (**`UPDATE_SLACK_TITLE`** environment variable): after
the photo uploads successfully, the job can call Gemini with a **text-only**
model (`GEMINI_TEXT_MODEL`, default `gemini-2.5-flash`), generate **one
satirical corporate-style phrase**, and update Slack’s **`title`** field (Cargo /
Job title) via **`users.profile.set`**. Enable it by setting **`UPDATE_SLACK_TITLE`**
to **`1`**, **`true`**, **`yes`**, or **`on`** in `.env` (see Environment variables below).
**This step is best-effort**: token scope, workspace policies, SCIM/HRIS, or Slack
API quirks can make the call return success while the visible title does not
match what was sent, or block updates entirely.

If that step fails, the job **logs a warning** and exits **0** without changing the
prior title.

## Requirements

- Python **3.12**
- Slack **user token** (`xoxp-…`) with **`users.profile:write`**
- **Gemini API key** from [Google AI Studio](https://aistudio.google.com/)

### Slack app (one-time)

1. Create an app at [api.slack.com/apps](https://api.slack.com/apps).
2. **OAuth & Permissions** → **User Token Scopes** → add `users.profile:write`.
3. Install (or reinstall) the app after scope changes and copy the **User OAuth Token**.

Profile updates via API also require **`Configure Profiles`** in the workspace admin (**Data source → API**) per Slack docs; Enterprise Grid workspaces may forbid members changing **their own** profile via API (**Org users cannot change their own profile details**).

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
day’s prompt list → `random.choice` on the image file list. With
**`UPDATE_SLACK_TITLE`**, Gemini’s phrase is trimmed when needed so it fits Slack’s length
constraints. Successful **`users.profile.set`** calls **log** `profile['title']`
as echoed by Slack. The seed is logged so you can replay image/prompt picks for
debugging.

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
| `GEMINI_TEXT_MODEL` | Text-capable Gemini id for **`UPDATE_SLACK_TITLE`** only (default `gemini-2.5-flash`). |
| `UPDATE_SLACK_TITLE` | Optional. If `1` / `true` / `yes` / `on`, generate and push **Cargo / job title** after each successful **`users.setPhoto`**, including runs that fall back to the **raw base photo** (no AI avatar) — text generation is still attempted. **May not apply or may disagree with the UI** depending on workspace controls and Slack behavior; treat as experimental. |
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
- **Optional Slack titles (`UPDATE_SLACK_TITLE`)**: off by default; turn on via env when
  you want the extra step. Even when enabled, **`title`** updates can **fail silently or
  disagree with the Slack UI** (workspace admin settings, SSO/SCIM, Enterprise rules,
  or token/user mismatch).
- **Title mismatch after `ok:true`**: the run prints **`describe_slack_token_user`**
  **before** writing the phrase — **`login=` / `user_id=` must be Camilo Henríquez’s
  account**. If another user installs the app, **`users.profile.set` updates THAT
  user’s Cargo**, while the modal you screenshot belongs to yours (old «programador…» unchanged).
