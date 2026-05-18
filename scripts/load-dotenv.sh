#!/usr/bin/env bash
# Load .env into the shell; skip comments, blanks, and lines that are not VAR=value.
# Avoids `source .env` failing when the file contains notes or URLs without '='.

load_dotenv() {
  local env_file="${1:-.env}"
  if [[ ! -f "$env_file" ]]; then
    echo "error: ${env_file} not found" >&2
    return 1
  fi
  while IFS= read -r line || [[ -n "${line}" ]]; do
    [[ -z "${line//[[:space:]]/}" ]] && continue
    # trim leading space for optional "export"
    line="${line#"${line%%[![:space:]]*}"}"
    [[ "${line}" == \#* ]] && continue
    [[ "${line}" == export\ * ]] && line="${line#export }"
    line="${line#"${line%%[![:space:]]*}"}"
    [[ -z "${line//[[:space:]]/}" ]] && continue
    [[ "${line}" == \#* ]] && continue
    if [[ ! "${line}" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
      continue
    fi
    export "$line"
  done <"${env_file}"
}
