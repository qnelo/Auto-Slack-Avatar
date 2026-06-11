"""Call Gemini image model with a base image and edit prompt."""

from __future__ import annotations

import importlib.metadata
import logging
import re
import time
from io import BytesIO
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types
from google.genai.errors import ClientError
from PIL import Image
from pillow_heif import register_heif_opener

register_heif_opener()
try:
    _pillow_heif_ver = importlib.metadata.version("pillow-heif")
except importlib.metadata.PackageNotFoundError:
    _pillow_heif_ver = "unknown"

_logger = logging.getLogger(__name__)

_RETRY_IN_MESSAGE_RE = re.compile(r"Please retry in ([0-9.]+)s", re.IGNORECASE)

# Max square edge for Gemini input (aligns with common "1K" ~1024px tier).
_GEMINI_INPUT_SIDE = 1024

_heif_support_logged = False


def _log_heif_support_once() -> None:
    global _heif_support_logged
    if _heif_support_logged:
        return
    _heif_support_logged = True
    _logger.info("HEIC/HEIF decode enabled (pillow-heif %s)", _pillow_heif_ver)


def _input_image_to_1k_square_png(image_path: Path) -> bytes:
    """Center-crop to square, resize to fixed edge length, return PNG bytes."""
    image = Image.open(image_path).convert("RGBA")
    width, height = image.size
    edge = min(width, height)
    left = (width - edge) // 2
    top = (height - edge) // 2
    image = image.crop((left, top, left + edge, top + edge))
    image = image.resize(
        (_GEMINI_INPUT_SIDE, _GEMINI_INPUT_SIDE),
        Image.Resampling.LANCZOS,
    )
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


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
    prepared_png = _input_image_to_1k_square_png(image_path)
    response = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_text(text=prompt),
            types.Part.from_bytes(data=prepared_png, mime_type="image/png"),
        ],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(
                aspect_ratio="1:1",
                image_size="512",
            ),
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
    _log_heif_support_once()
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
