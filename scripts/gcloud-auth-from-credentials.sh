#!/usr/bin/env bash
# When docker-compose.gcp-sa.yml sets GOOGLE_APPLICATION_CREDENTIALS, gcloud and
# docker-credential-gcloud still default to the active account in ~/.config/gcloud
# if we do not activate this key explicitly.

activate_gcloud_sa_from_credentials() {
  if [[ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" && -f "${GOOGLE_APPLICATION_CREDENTIALS}" ]]; then
    gcloud auth activate-service-account --key-file="${GOOGLE_APPLICATION_CREDENTIALS}" --quiet
  fi
}
