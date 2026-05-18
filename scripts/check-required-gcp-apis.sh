#!/usr/bin/env bash
# Fail fast if required APIs are off. Deploy service accounts usually cannot call
# serviceusage.services.enable; a project Owner must enable APIs once.

check_required_gcp_apis() {
  : "${GCP_PROJECT:?set GCP_PROJECT}"

  local apis=(
    cloudresourcemanager.googleapis.com
    serviceusage.googleapis.com
    run.googleapis.com
    artifactregistry.googleapis.com
    cloudscheduler.googleapis.com
  )

  local list_out
  if ! list_out="$(gcloud services list --enabled --project="${GCP_PROJECT}" --format='value(name)' 2>&1)"; then
    echo "error: cannot list enabled APIs for project ${GCP_PROJECT}." >&2
    echo "This often means Cloud Resource Manager or Service Usage API is disabled. A project" >&2
    echo "Owner must enable APIs once (example below). Deploy SAs cannot enable billing/APIs." >&2
    echo "" >&2
    echo "  gcloud services enable ${apis[*]} --project=${GCP_PROJECT}" >&2
    echo "" >&2
    echo "gcloud said:" >&2
    echo "$list_out" >&2
    exit 1
  fi

  local missing=()
  local a
  for a in "${apis[@]}"; do
    if ! grep -q "/services/${a}" <<<"${list_out}"; then
      missing+=("$a")
    fi
  done

  if ((${#missing[@]})); then
    echo "error: these APIs are not enabled on ${GCP_PROJECT}: ${missing[*]}" >&2
    echo "A project Owner must run once (the deploy service account cannot enable them):" >&2
    echo "" >&2
    echo "  gcloud services enable ${missing[*]} --project=${GCP_PROJECT}" >&2
    echo "" >&2
    exit 1
  fi
}
