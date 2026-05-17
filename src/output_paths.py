"""Output filename helper for generated avatars."""

from __future__ import annotations

from datetime import datetime


def avatar_output_filename(now: datetime) -> str:
    """Build filename: avatar_YYYY-MM-DD_HHMMSS.png for local `now`."""
    stamp = now.strftime("%Y-%m-%d_%H%M%S")
    return f"avatar_{stamp}.png"
