"""Resize avatar for Slack and upload via users.setPhoto."""

from __future__ import annotations

from io import BytesIO

import requests
from PIL import Image

SLACK_SET_PHOTO_URL = "https://slack.com/api/users.setPhoto"


def image_bytes_to_slack_square_png(data: bytes, side: int = 1024) -> bytes:
    """Center-crop to square and resize to `side` (512–1024 for Slack)."""
    if side < 512 or side > 1024:
        msg = "side must be between 512 and 1024 inclusive"
        raise ValueError(msg)
    image = Image.open(BytesIO(data)).convert("RGBA")
    width, height = image.size
    edge = min(width, height)
    left = (width - edge) // 2
    top = (height - edge) // 2
    image = image.crop((left, top, left + edge, top + edge))
    image = image.resize((side, side), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def upload_profile_photo(
    *,
    token: str,
    image_bytes: bytes,
    filename: str = "avatar.png",
) -> None:
    """Upload PNG bytes as the authenticated user's profile photo."""
    headers = {"Authorization": f"Bearer {token}"}
    files = {
        "image": (
            filename,
            image_bytes,
            "image/png",
        ),
    }
    response = requests.post(
        SLACK_SET_PHOTO_URL,
        headers=headers,
        files=files,
        timeout=120,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        err = payload.get("error", "unknown_error")
        msg = f"Slack users.setPhoto failed: {err}"
        raise RuntimeError(msg)
