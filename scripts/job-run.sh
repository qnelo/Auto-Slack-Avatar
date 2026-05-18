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
: "${CLOUD_RUN_JOB_NAME:?set CLOUD_RUN_JOB_NAME in .env}"

gcloud config set project "${GCP_PROJECT}" --quiet
check_required_gcp_apis

gcloud run jobs execute "${CLOUD_RUN_JOB_NAME}" \
  --region="${GCP_REGION}" \
  --project="${GCP_PROJECT}" \
  --wait
