"""Load configuration from environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _truthy_env(name: str) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _parse_optional_seed(raw: str | None) -> int | None:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    return int(text, 10)


@dataclass(frozen=True)
class Config:
    """Runtime configuration for one avatar run."""

    slack_user_token: str
    gemini_api_key: str
    gemini_image_model: str
    strict_gemini: bool
    timezone: str
    assets_dir: Path
    prompts_path: Path
    output_dir: Path
    run_seed_override: int | None

    @classmethod
    def from_environ(cls) -> Config:
        """Build config from process environment (after load_dotenv)."""
        slack = os.environ.get("SLACK_USER_TOKEN", "").strip()
        if not slack:
            msg = "SLACK_USER_TOKEN is required"
            raise ValueError(msg)
        gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not gemini_key:
            msg = "GEMINI_API_KEY is required"
            raise ValueError(msg)
        model = os.environ.get(
            "GEMINI_IMAGE_MODEL",
            "gemini-2.5-flash-image",
        ).strip()
        if not model:
            msg = "GEMINI_IMAGE_MODEL must not be empty"
            raise ValueError(msg)
        strict = _truthy_env("STRICT_GEMINI")
        tz = os.environ.get("TZ", "UTC").strip() or "UTC"
        assets = Path(os.environ.get("ASSETS_DIR", "assets/images"))
        prompts = Path(os.environ.get("PROMPTS_PATH", "prompts.json"))
        out = Path(os.environ.get("OUTPUT_DIR", "output"))
        seed = _parse_optional_seed(os.environ.get("RUN_SEED"))
        return cls(
            slack_user_token=slack,
            gemini_api_key=gemini_key,
            gemini_image_model=model,
            strict_gemini=strict,
            timezone=tz,
            assets_dir=assets,
            prompts_path=prompts,
            output_dir=out,
            run_seed_override=seed,
        )
