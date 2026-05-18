#!/usr/bin/env bash
set -euo pipefail
set +H
cd "$(dirname "$0")/.."
if [[ ! -f .env ]]; then
  echo "error: .env not found in repo root" >&2
  exit 1
fi
# shellcheck source=scripts/load-dotenv.sh
source "$(dirname "$0")/load-dotenv.sh"
# shellcheck source=scripts/gcloud-auth-from-credentials.sh
source "$(dirname "$0")/gcloud-auth-from-credentials.sh"
# shellcheck source=scripts/check-required-gcp-apis.sh
source "$(dirname "$0")/check-required-gcp-apis.sh"
load_dotenv .env
activate_gcloud_sa_from_credentials

: "${GCP_PROJECT:?set GCP_PROJECT in .env}"
: "${GCP_REGION:?set GCP_REGION in .env}"
: "${AR_REPO:?set AR_REPO in .env}"
: "${IMAGE_NAME:?set IMAGE_NAME in .env}"
: "${IMAGE_TAG:?set IMAGE_TAG in .env}"
: "${CLOUD_RUN_JOB_NAME:?set CLOUD_RUN_JOB_NAME in .env}"

if [[ -n "${IMAGE_URI:-}" ]]; then
  uri="$IMAGE_URI"
else
  uri="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT}/${AR_REPO}/${IMAGE_NAME}:${IMAGE_TAG}"
fi

tmp_yaml="$(mktemp)"
trap 'rm -f "$tmp_yaml"' EXIT

python3 scripts/write_runtime_env_yaml.py >"$tmp_yaml"

gcloud config set project "${GCP_PROJECT}" --quiet
check_required_gcp_apis

args=(
  gcloud run jobs deploy "${CLOUD_RUN_JOB_NAME}"
  --image="${uri}"
  --region="${GCP_REGION}"
  --project="${GCP_PROJECT}"
  --env-vars-file="${tmp_yaml}"
  --tasks=1
  --max-retries="${CLOUD_RUN_MAX_RETRIES:-1}"
  --task-timeout="${CLOUD_RUN_TASK_TIMEOUT:-10m}"
  --quiet
)

if [[ -n "${CLOUD_RUN_JOB_SERVICE_ACCOUNT:-}" ]]; then
  args+=(--tasks-service-account="${CLOUD_RUN_JOB_SERVICE_ACCOUNT}")
fi

"${args[@]}"
