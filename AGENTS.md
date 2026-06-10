# AGENTS.md

Extra context for coding agents working on this repository. Human-oriented docs live in [README.md](README.md). This file follows the open [AGENTS.md](https://agents.md/) convention (plain Markdown, no required schema).

## Project overview

Python **3.12** CLI + Docker image: picks a weekday prompt from [prompts.json](prompts.json) (or the **`holidays`** list when today matches [vacations.json](vacations.json), optional and gitignored with [vacations.example.json](vacations.example.json) as template), a random base photo from [assets/images](assets/images), calls **Google Gemini** for an edited image, post-processes to a **1024×1024** PNG, optionally updates Slack **job title**, and uploads the photo via **`users.setPhoto`**. Entry point: [src/run_daily.py](src/run_daily.py). Configuration: [src/config.py](src/config.py) and `.env`.

## Local development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
python -m src.run_daily
```

Lint / format (Ruff; see [pyproject.toml](pyproject.toml)):

```bash
ruff check src
ruff format src
```

## Docker

- **App image** ([Dockerfile](Dockerfile)): Cloud Run Job / local runs; includes `assets/images` in the image; **must not** `COPY .env` or blind `COPY .` from the repo root.
- **`.env` is not in** [`.dockerignore`](.dockerignore), so it is part of the **build context** for the app image—do not add Dockerfile instructions that bake secrets into layers.
- **One-shot local job**: `make run-local` (or `docker compose run --rm avatar-job`); `make build-local` builds the app image (`avatar-job`).
- **Deploy toolchain image** ([Dockerfile.deploy](Dockerfile.deploy)) + `deploy` service in [docker-compose.yml](docker-compose.yml): `gcloud`, Docker CLI (via host socket), `make`. Run Makefile targets **inside** this container.

Full GCP rollout from the host (only Docker + Compose required on the host):

```bash
docker compose build deploy
docker compose run --rm deploy make deploy
```

Useful targets inside `deploy`: `make docker-push`, `make deploy-job`, `make deploy-scheduler`, `make job-run`.

## Deploy / GCP

- **No Secret Manager**: runtime env for the Cloud Run Job comes from `.env` via [scripts/write_runtime_env_yaml.py](scripts/write_runtime_env_yaml.py) and `gcloud run jobs deploy --env-vars-file`. Deploy-only keys (`GCP_*`, `SCHEDULER_*`, `AR_*`, `IMAGE_*`, etc.) are **not** passed to Python; see [.env.example](.env.example).
- **Auth inside `deploy`**:
  - **Service account** (default for this repo): JSON on the host at `credentials/gcp-sa.json` (default) or path **`GCP_SERVICE_ACCOUNT_KEY`**; set **`COMPOSE_FILE=docker-compose.yml:docker-compose.gcp-sa.yml`** in `.env` (or pass `-f` flags). Scripts run **`gcloud auth activate-service-account`** so the **image push and deploy use the SA**, not the host user. That SA needs IAM for Artifact Registry push, Cloud Run Job deploy, **and Cloud Scheduler job create/update** (e.g. **`roles/cloudscheduler.admin`**), not only the invoker SA used at cron time. Do not store the key body in `.env`.
  - **Human user**: merge [docker-compose.gcloud-user.yml](docker-compose.gcloud-user.yml) into **`COMPOSE_FILE`** and run `gcloud auth login` in the `deploy` container so `~/.config/gcloud` is mounted from the host.
- [scripts/docker-push.sh](scripts/docker-push.sh), [scripts/deploy-job.sh](scripts/deploy-job.sh), [scripts/deploy-scheduler.sh](scripts/deploy-scheduler.sh), [scripts/job-run.sh](scripts/job-run.sh) assume `.env` is **bash-sourceable** from the repo root inside `/workspace`.
- Cloud Scheduler **create vs update**: [scripts/deploy-scheduler.sh](scripts/deploy-scheduler.sh) uses `gcloud scheduler jobs describe` then `update http` or `create http` against the Run **v1** `jobs:run` URI for `CLOUD_RUN_JOB_NAME`.
- All **code** and user-facing strings you add should stay in **English**.

## Security

- Never commit `.env`, **`credentials/gcp-sa.json`**, or any service account JSON.
- `SLACK_USER_TOKEN` and `GEMINI_API_KEY` are secrets; they land in Cloud Run Job configuration when deploying—treat GCP IAM on that resource accordingly.

## Commits and PRs

Only create commits when the user explicitly asks. Do not commit `.env` or credential files.
