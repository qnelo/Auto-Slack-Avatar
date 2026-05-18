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
: "${SCHEDULER_JOB_NAME:?set SCHEDULER_JOB_NAME in .env}"
: "${SCHEDULER_CRON:?set SCHEDULER_CRON in .env}"
: "${SCHEDULER_TIME_ZONE:?set SCHEDULER_TIME_ZONE in .env}"
: "${SCHEDULER_SERVICE_ACCOUNT:?set SCHEDULER_SERVICE_ACCOUNT in .env}"

gcloud config set project "${GCP_PROJECT}" --quiet
check_required_gcp_apis

run_uri="https://${GCP_REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${GCP_PROJECT}/jobs/${CLOUD_RUN_JOB_NAME}:run"

if gcloud scheduler jobs describe "${SCHEDULER_JOB_NAME}" \
  --location="${GCP_REGION}" \
  --project="${GCP_PROJECT}" &>/dev/null
then
  gcloud scheduler jobs update http "${SCHEDULER_JOB_NAME}" \
    --location="${GCP_REGION}" \
    --project="${GCP_PROJECT}" \
    --schedule="${SCHEDULER_CRON}" \
    --time-zone="${SCHEDULER_TIME_ZONE}" \
    --uri="${run_uri}" \
    --http-method=POST \
    --oauth-service-account-email="${SCHEDULER_SERVICE_ACCOUNT}" \
    --quiet
else
  gcloud scheduler jobs create http "${SCHEDULER_JOB_NAME}" \
    --location="${GCP_REGION}" \
    --project="${GCP_PROJECT}" \
    --schedule="${SCHEDULER_CRON}" \
    --time-zone="${SCHEDULER_TIME_ZONE}" \
    --uri="${run_uri}" \
    --http-method=POST \
    --oauth-service-account-email="${SCHEDULER_SERVICE_ACCOUNT}" \
    --quiet
fi
