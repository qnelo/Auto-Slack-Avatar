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

if [[ -n "${IMAGE_URI:-}" ]]; then
  uri="$IMAGE_URI"
else
  uri="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT}/${AR_REPO}/${IMAGE_NAME}:${IMAGE_TAG}"
fi

gcloud config set project "${GCP_PROJECT}" --quiet
check_required_gcp_apis
gcloud auth configure-docker "${GCP_REGION}-docker.pkg.dev" --quiet
if [[ ! -f vacations.json ]]; then
  cp vacations.example.json vacations.json
fi
docker build -t "${uri}" .
docker push "${uri}"
