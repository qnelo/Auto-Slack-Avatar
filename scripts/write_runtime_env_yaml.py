#!/usr/bin/env python3
"""Emit YAML for gcloud run jobs deploy --env-vars-file (runtime keys only)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

RUNTIME_KEYS = frozenset(
    {
        "SLACK_USER_TOKEN",
        "GEMINI_API_KEY",
        "GEMINI_IMAGE_MODEL",
        "GEMINI_TEXT_MODEL",
        "UPDATE_SLACK_TITLE",
        "STRICT_GEMINI",
        "TZ",
        "RUN_SEED",
        "ASSETS_DIR",
        "PROMPTS_PATH",
        "OUTPUT_DIR",
    }
)


def _strip_quotes(val: str) -> str:
    if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
        return val[1:-1]
    return val


def parse_dotenv(path: Path) -> dict[str, str]:
    """Parse KEY=VALUE lines; ignore comments and keys not in RUNTIME_KEYS."""
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if key not in RUNTIME_KEYS:
            continue
        val = _strip_quotes(val.strip())
        result[key] = val
    return result


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    env_path = root / ".env"
    if not env_path.is_file():
        print("error: .env not found in repo root", file=sys.stderr)
        sys.exit(1)
    data = parse_dotenv(env_path)
    if "SLACK_USER_TOKEN" not in data or not data["SLACK_USER_TOKEN"]:
        print(
            "error: SLACK_USER_TOKEN missing or empty in .env",
            file=sys.stderr,
        )
        sys.exit(1)
    if "GEMINI_API_KEY" not in data or not data["GEMINI_API_KEY"]:
        print(
            "error: GEMINI_API_KEY missing or empty in .env",
            file=sys.stderr,
        )
        sys.exit(1)
    for key in sorted(data.keys()):
        print(f"{key}: {json.dumps(data[key])}")


if __name__ == "__main__":
    main()
