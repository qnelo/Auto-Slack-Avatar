"""CLI entrypoint: pick assets, call Gemini, save output, update Slack."""

from __future__ import annotations

import logging
import random
import time
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv
from google.genai.errors import ClientError
from slack_sdk import WebClient

from src.config import Config
from src.gemini_image import generate_edited_png
from src.gemini_title import generate_slack_profile_title
from src.output_paths import avatar_output_filename
from src.prompts_json import WEEKDAY_KEYS, combine_with_base, load_prompts
from src.select_assets import list_image_paths
from src.slack_photo import (
    image_bytes_to_slack_square_png,
    upload_profile_photo,
)
from src.slack_profile import describe_slack_token_user, set_profile_title
from src.vacations_json import is_vacation_today, load_vacations

_logger = logging.getLogger(__name__)


def _gemini_quota_fallback_eligible(exc: ClientError) -> bool:
    """True for exhausted quota / rate limits, not malformed requests."""
    if exc.code != 429:
        return False
    blob = f"{exc.message!s} {exc.details!s}"
    lowered = blob.lower()
    if "resource_exhausted" in lowered:
        return True
    return "quota exceeded" in lowered and "limit: 0" in lowered


def compute_run_seed(override: int | None) -> int:
    """Return override seed or current Unix seconds as int."""
    if override is not None:
        return override
    return int(time.time())


def weekday_key_for_datetime(moment: datetime) -> str:
    """Map weekday (Monday=0) to prompts.json key."""
    idx = moment.weekday()
    return WEEKDAY_KEYS[idx]


def run() -> int:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
    )
    try:
        cfg = Config.from_environ()
    except (OSError, ValueError) as exc:
        _logger.exception("Configuration error: %s", exc)
        return 1

    run_seed = compute_run_seed(cfg.run_seed_override)
    random.seed(run_seed)
    _logger.info("run_seed=%s", run_seed)

    try:
        zone = ZoneInfo(cfg.timezone)
    except ZoneInfoNotFoundError:
        _logger.exception("Invalid TZ %r", cfg.timezone)
        return 1

    now = datetime.now(zone)
    wkey = weekday_key_for_datetime(now)
    _logger.info(
        "local_time=%s weekday=%s tz=%s",
        now.isoformat(),
        wkey,
        cfg.timezone,
    )

    try:
        bundle = load_prompts(cfg.prompts_path)
        vacations = load_vacations(cfg.vacations_path)
        if vacations is not None:
            vacation_today = is_vacation_today(vacations)
            _logger.info(
                "vacations_timezone=%s vacation_dates_loaded=%s "
                "vacation_today=%s",
                vacations.timezone.key,
                len(vacations.dates),
                vacation_today,
            )
        else:
            vacation_today = False
            _logger.info("vacations_file=missing vacation_today=false")

        if vacations is not None and vacation_today:
            prompt_pool = bundle.prompts_for_holidays()
            prompt_source = "holidays"
        else:
            prompt_pool = bundle.prompts_for_weekday(wkey)
            prompt_source = wkey

        day_prompt = random.choice(prompt_pool)
        prompt = combine_with_base(bundle.base_prompt, day_prompt)
        images = list_image_paths(cfg.assets_dir)
        image_path = random.choice(images)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        _logger.exception("Assets or prompts error: %s", exc)
        return 1

    _logger.info("prompt_source=%s", prompt_source)
    _logger.info("base_image=%s", image_path)
    _logger.info("day_prompt=%s", day_prompt)
    _logger.info("prompt=%s", prompt)

    try:
        raw_png = generate_edited_png(
            api_key=cfg.gemini_api_key,
            model=cfg.gemini_image_model,
            image_path=image_path,
            prompt=prompt,
        )
    except ClientError as exc:
        if cfg.strict_gemini or not _gemini_quota_fallback_eligible(exc):
            _logger.exception("Gemini image generation failed")
            return 1
        _logger.warning(
            "Gemini quota or rate limit hit; continuing with the base photo "
            "without AI editing. Fix API quota or set STRICT_GEMINI=1 to fail "
            "hard.",
        )
        raw_png = image_path.read_bytes()
    except Exception:
        _logger.exception("Gemini image generation failed")
        return 1

    try:
        slack_png = image_bytes_to_slack_square_png(raw_png, side=1024)
    except Exception:
        _logger.exception("Image post-process failed")
        return 1

    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    out_name = avatar_output_filename(now)
    out_path = cfg.output_dir / out_name
    try:
        out_path.write_bytes(slack_png)
    except OSError:
        _logger.exception("Failed writing %s", out_path)
        return 1
    _logger.info("saved_output=%s", out_path)

    slack_client = WebClient(token=cfg.slack_user_token, timeout=120)
    try:
        upload_profile_photo(
            client=slack_client,
            image_bytes=slack_png,
            filename=out_name,
        )
    except Exception:
        _logger.exception("Slack upload failed (file saved at %s)", out_path)
        return 1

    _logger.info("Slack profile photo updated.")

    if cfg.update_slack_title:
        try:
            _logger.info(
                "Before title update, Slack token is: %s",
                describe_slack_token_user(client=slack_client),
            )
            phrase = generate_slack_profile_title(
                api_key=cfg.gemini_api_key,
                model=cfg.gemini_text_model,
            )
            set_profile_title(client=slack_client, title=phrase)
            _logger.info("Slack profile title updated (Gemini): %s", phrase)
        except Exception:
            _logger.warning(
                "Slack profile title update skipped (title left unchanged)",
                exc_info=True,
            )

    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
