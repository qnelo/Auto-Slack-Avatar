"""Weekday prompts from JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

BASE_PROMPT_KEY = "base_prompt"

WEEKDAY_KEYS: tuple[str, ...] = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


@dataclass(frozen=True)
class PromptsBundle:
    """Global Slack-avatar constraints plus per-weekday stylistic prompts."""

    base_prompt: str
    by_weekday: dict[str, list[str]]

    def prompts_for_weekday(self, wkey: str) -> list[str]:
        """Return weekday prompt strings (stylistic part only)."""
        return self.by_weekday[wkey]


def combine_with_base(base: str, day_prompt: str) -> str:
    """Prepend invariant Slack-avatar instructions to the day's prompt."""
    b = base.strip()
    d = day_prompt.strip()
    if not d:
        return b
    return f"{b}\n\n{d}"


def load_prompts(path: Path) -> PromptsBundle:
    """Load prompts: base_prompt + weekday lists."""
    if not path.is_file():
        msg = f"Prompts file not found: {path}"
        raise FileNotFoundError(msg)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        msg = "prompts.json must be a JSON object"
        raise ValueError(msg)

    allowed_keys = frozenset((BASE_PROMPT_KEY, *WEEKDAY_KEYS))
    unknown = set(data.keys()) - allowed_keys
    if unknown:
        msg = f"prompts.json has unknown keys: {sorted(unknown)}"
        raise ValueError(msg)

    if BASE_PROMPT_KEY not in data:
        msg = f"prompts.json missing key: {BASE_PROMPT_KEY}"
        raise KeyError(msg)
    raw_base = data[BASE_PROMPT_KEY]
    if not isinstance(raw_base, str):
        msg = f"prompts.json['{BASE_PROMPT_KEY}'] must be a string"
        raise TypeError(msg)
    base = raw_base.strip()
    if not base:
        msg = f"prompts.json['{BASE_PROMPT_KEY}'] must be non-empty"
        raise ValueError(msg)

    weekdays: dict[str, list[str]] = {}
    for key in WEEKDAY_KEYS:
        if key not in data:
            msg = f"prompts.json missing key: {key}"
            raise KeyError(msg)
        val = data[key]
        is_str_list = isinstance(val, list) and all(
            isinstance(x, str) for x in val
        )
        if not is_str_list:
            msg = f"prompts.json['{key}'] must be a list of strings"
            raise TypeError(msg)
        strings = [s.strip() for s in val if s.strip()]
        if not strings:
            msg = f"prompts.json['{key}'] must contain at least one prompt"
            raise ValueError(msg)
        weekdays[key] = strings

    return PromptsBundle(base_prompt=base, by_weekday=weekdays)
