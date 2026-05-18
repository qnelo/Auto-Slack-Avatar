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

Equivalent: `make build-local` then `make run-local` from the repo root (host only needs Docker).

Ensure `.env` exists and mount paths in `docker-compose.yml` match your machine.

## Deploy to GCP (Cloud Run Job)

The production shape is a **Cloud Run Job** (one container run per trigger), an image in **Artifact Registry**, and **Cloud Scheduler** hitting the Job run API on a cron you configure in `.env`. **Secret Manager is not used**; the Makefile injects env vars from your `.env` into the Job at deploy time.

**On your machine you only need Docker and Docker Compose**—no host install of `gcloud`. Deploy tooling runs inside a second image ([`Dockerfile.deploy`](Dockerfile.deploy)) via the `deploy` service in [`docker-compose.yml`](docker-compose.yml).

1. Copy [`.env.example`](.env.example) to `.env` and fill **application** variables plus **GCP** / **Scheduler** variables (`GCP_PROJECT`, `GCP_REGION`, `AR_REPO`, `IMAGE_NAME`, `IMAGE_TAG`, `CLOUD_RUN_JOB_NAME`, `SCHEDULER_*`, etc.). Never commit `.env`.
2. Enable GCP APIs **once** as a **project Owner** (or another principal with `serviceusage.services.enable`). A **deploy service account cannot** enable APIs for you. Example:

   ```bash
   gcloud services enable \
     cloudresourcemanager.googleapis.com \
     serviceusage.googleapis.com \
     run.googleapis.com \
     artifactregistry.googleapis.com \
     cloudscheduler.googleapis.com \
     --project=YOUR_PROJECT_ID
   ```

   Or use **APIs & Services → Enable APIs** in the Cloud Console. Deploy scripts call [`scripts/check-required-gcp-apis.sh`](scripts/check-required-gcp-apis.sh) and exit early with the same `gcloud services enable` hint if something is missing.
3. Create the Artifact Registry Docker repository (see earlier errors if it is missing). Then wire **two different service accounts** in IAM:
   - **Deploy service account** (the one whose **JSON key** you mount for `make deploy` / `docker-push`): must be able to push images, deploy the Cloud Run Job, and **create/update Cloud Scheduler jobs** (the script runs `gcloud scheduler jobs create|update`). Typical project-level roles: `roles/artifactregistry.writer`, `roles/run.developer` (or `roles/run.admin`), and **`roles/cloudscheduler.admin`** (covers `cloudscheduler.jobs.create` / `update`; a narrow custom role is possible but admin is the usual choice).
   - **Scheduler invoker** (`SCHEDULER_SERVICE_ACCOUNT` in `.env`): the account Cloud Scheduler uses for **OAuth** when it **POSTs** to the Cloud Run Job run URL. It needs permission to **run** that job, e.g. `roles/run.developer` or a custom role including `run.jobs.run`. It does **not** replace the deploy SA for `deploy-scheduler.sh`.

   Example (replace `DEPLOY_SA_EMAIL` with your key’s service account):

   ```bash
   PROJECT_ID=your-gcp-project-id
   DEPLOY_SA_EMAIL=your-deploy-sa@${PROJECT_ID}.iam.gserviceaccount.com

   gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
     --member="serviceAccount:${DEPLOY_SA_EMAIL}" --role="roles/cloudscheduler.admin"
   ```

4. **Authenticate for `gcloud` / Artifact Registry** (pick one):
   - **Service account key** (recommended): download a JSON key from GCP IAM, save it as **`credentials/gcp-sa.json`** (path is gitignored). In `.env` set:
     - `COMPOSE_FILE=docker-compose.yml:docker-compose.gcp-sa.yml`  
     Optionally set **`GCP_SERVICE_ACCOUNT_KEY`** if the file lives elsewhere on the host (default `./credentials/gcp-sa.json`). The fragment mounts it read-only at `/workspace/credentials/gcp-sa.json` and sets **`GOOGLE_APPLICATION_CREDENTIALS`**; deploy scripts call **`gcloud auth activate-service-account`**, so **the host user’s gcloud login is not used**. Do **not** paste the JSON into `.env`—only the host path / compose wiring.
   - **Human user login**: add [`docker-compose.gcloud-user.yml`](docker-compose.gcloud-user.yml) to **`COMPOSE_FILE`** (e.g. `docker-compose.yml:docker-compose.gcloud-user.yml`) so **`~/.config/gcloud`** is mounted from the host, then run `docker compose run --rm deploy gcloud auth login` once. Do **not** merge [`docker-compose.gcp-sa.yml`](docker-compose.gcp-sa.yml) unless you intend to use a key as well.
5. Build the deploy image once if needed: `docker compose build deploy`.
6. Full rollout (build/push app image, update Job, create/update Scheduler):

   ```bash
   docker compose run --rm deploy make deploy
   ```

   With a service account (after `COMPOSE_FILE` includes the fragment), the same command works; Compose merges [`docker-compose.gcp-sa.yml`](docker-compose.gcp-sa.yml) automatically when `COMPOSE_FILE` is set in `.env`.

   Convenience on the host: `make deploy-compose-sa` runs `make deploy` inside the deploy container **with** the SA compose files.

   Other targets (run inside the same `deploy` service): `make docker-push`, `make deploy-job`, `make deploy-scheduler`, `make job-run` (one-off Job execution with `--wait`).

The default [`docker-compose.yml`](docker-compose.yml) mounts the repo and the Docker socket (build/push use the **host** Docker daemon). It **does not** mount `~/.config/gcloud` or `~/.docker` so deploy runs do not inherit a random user login from the host. **`gcloud auth configure-docker`** writes **`/root/.docker`** inside the container; the **host** Docker daemon still performs `docker push` via the socket.

[`Makefile`](Makefile) and [`scripts/`](scripts/) are intended to run **inside** the `deploy` container. The app [`Dockerfile`](Dockerfile) must **not** `COPY .env`; `.env` is only for local/compose and deploy injection.

For agent-oriented commands and conventions, see [`AGENTS.md`](AGENTS.md).

### Application environment variables

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

### GCP and Scheduler (deploy via `deploy` container)

See [`.env.example`](.env.example) for `GCP_*`, `AR_REPO`, `IMAGE_*`, `CLOUD_RUN_*`, `SCHEDULER_*`, and optional **`GCP_SERVICE_ACCOUNT_KEY`** / **`COMPOSE_FILE`** + [`docker-compose.gcp-sa.yml`](docker-compose.gcp-sa.yml) for service-account auth. Application variables above are the ones passed to Cloud Run (runtime); deploy-only keys are read by [`scripts/`](scripts/) and must not be required inside the Python process.

## Lint / format (PEP8 via Ruff)

```bash
ruff check src
ruff format src
```

## Scheduling

- **GCP**: use Cloud Scheduler with `make deploy` (or `make deploy-scheduler`) so the schedule stays in sync with [`.env`](.env.example) (`SCHEDULER_CRON`, `SCHEDULER_TIME_ZONE`).
- **Elsewhere**: GitHub Actions `schedule`, host `cron`, or `docker compose run avatar-job` as a one-shot.

## Troubleshooting

- **`cloudscheduler.jobs.create` PERMISSION_DENIED** on `deploy-scheduler`: the **deploy** service account (JSON used by `make deploy`) must manage Scheduler resources—grant **`roles/cloudscheduler.admin`** at project level (see step 3). This is separate from **`SCHEDULER_SERVICE_ACCOUNT`**, which only **invokes** the Cloud Run Job when the schedule fires.
- **`SERVICE_DISABLED` / Cloud Resource Manager / “Permission denied to enable service”**: enable the APIs in the Console, or run the `gcloud services enable …` block in the **Deploy to GCP** section **as a human Owner**—not with the deploy service account.
- **`Permission denied` on `~/.docker/config.json` when running `docker compose` on the host**: the **host** Docker CLI reads that file before starting containers; fix ownership with `chown`/`chmod` on the host (this is unrelated to in-container `/root/.docker`).
- **Deploy with service account**: put the JSON in **`credentials/gcp-sa.json`**, set `COMPOSE_FILE=docker-compose.yml:docker-compose.gcp-sa.yml` in `.env`, then run compose (or `make deploy-compose-sa`). If the file is missing, the container will fail to start the bind mount.
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
