"""Call Gemini image model with a base image and edit prompt."""

from __future__ import annotations

import logging
import mimetypes
import re
import time
from io import BytesIO
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types
from google.genai.errors import ClientError
from PIL import Image

_logger = logging.getLogger(__name__)

_RETRY_IN_MESSAGE_RE = re.compile(r"Please retry in ([0-9.]+)s", re.IGNORECASE)


def _mime_for_path(image_path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(image_path))
    if guessed:
        return guessed
    suf = image_path.suffix.lower()
    if suf == ".png":
        return "image/png"
    if suf in (".jpg", ".jpeg"):
        return "image/jpeg"
    if suf == ".webp":
        return "image/webp"
    if suf == ".heic":
        return "image/heic"
    if suf == ".heif":
        return "image/heif"
    return "application/octet-stream"


def _free_tier_quota_unavailable(exc: ClientError) -> bool:
    """True when free-tier quota is exhausted (no point retrying)."""
    blob = f"{exc.message!s} {exc.details!s}".lower()
    return "limit: 0" in blob and "quota exceeded" in blob


def _retry_seconds_from_client_error(exc: ClientError) -> float:
    """Best-effort delay from RetryInfo or error message."""
    details: Any = exc.details
    try:
        if isinstance(details, dict):
            err = details.get("error", details)
            if isinstance(err, dict):
                for item in err.get("details", []) or []:
                    if not isinstance(item, dict):
                        continue
                    if not str(item.get("@type", "")).endswith("RetryInfo"):
                        continue
                    raw = str(item.get("retryDelay", ""))
                    if raw.endswith("s"):
                        return max(1.0, float(raw[:-1]))
    except (TypeError, ValueError):
        pass
    if exc.message:
        m = _RETRY_IN_MESSAGE_RE.search(exc.message)
        if m:
            return max(1.0, float(m.group(1)))
    return 10.0


def _generate_edited_png_once(
    *,
    api_key: str,
    model: str,
    image_path: Path,
    prompt: str,
) -> bytes:
    """Single API call; raises :class:`ClientError` on HTTP/API errors."""
    client = genai.Client(api_key=api_key)
    raw = image_path.read_bytes()
    mime = _mime_for_path(image_path)
    response = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_text(text=prompt),
            types.Part.from_bytes(data=raw, mime_type=mime),
        ],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="1:1"),
        ),
    )
    parts = getattr(response, "parts", None)
    if parts is None:
        msg = "Unexpected API response: missing parts"
        raise RuntimeError(msg)

    for part in parts:
        if part.inline_data is None:
            continue
        gen_image = part.as_image()
        if gen_image is None or not gen_image.image_bytes:
            continue
        pil_image = Image.open(BytesIO(gen_image.image_bytes)).convert("RGBA")
        out_buf = BytesIO()
        pil_image.save(out_buf, format="PNG")
        return out_buf.getvalue()

    text = getattr(response, "text", "") or ""
    msg = f"Gemini did not return an image. Model text: {text!r}"
    raise RuntimeError(msg)


def generate_edited_png(
    *,
    api_key: str,
    model: str,
    image_path: Path,
    prompt: str,
    max_429_attempts: int = 4,
) -> bytes:
    """Return PNG bytes produced by the image model.

    Retries HTTP 429 a few times when the API suggests a retry delay, except
    when the free tier reports ``limit: 0`` (no point waiting).
    """
    last: ClientError | None = None
    for attempt in range(max_429_attempts):
        try:
            return _generate_edited_png_once(
                api_key=api_key,
                model=model,
                image_path=image_path,
                prompt=prompt,
            )
        except ClientError as exc:
            last = exc
            if exc.code != 429:
                raise
            if _free_tier_quota_unavailable(exc):
                _logger.warning(
                    "Gemini 429: no free-tier quota left; not retrying.",
                )
                raise
            delay = _retry_seconds_from_client_error(exc)
            if attempt + 1 >= max_429_attempts:
                raise
            _logger.warning(
                "Gemini rate limited (429), retry %s/%s after %.1fs",
                attempt + 1,
                max_429_attempts,
                delay,
            )
            time.sleep(delay)
    assert last is not None
    raise last

