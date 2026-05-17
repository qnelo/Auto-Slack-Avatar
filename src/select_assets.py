"""List and pick base images from assets directory."""

from __future__ import annotations

from pathlib import Path

IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif"},
)


def list_image_paths(assets_dir: Path) -> list[Path]:
    """Return sorted image paths under assets_dir (non-recursive)."""
    if not assets_dir.is_dir():
        msg = f"Assets directory not found: {assets_dir}"
        raise FileNotFoundError(msg)
    paths: list[Path] = []
    for p in assets_dir.iterdir():
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS:
            paths.append(p)
    paths.sort(key=lambda x: x.name.lower())
    if not paths:
        msg = f"No images found in {assets_dir}"
        raise FileNotFoundError(msg)
    return paths
