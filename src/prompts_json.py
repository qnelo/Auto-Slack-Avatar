"""Weekday prompts from JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

BASE_PROMPT_KEY = "base_prompt"
HOLIDAYS_KEY = "holidays"

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
    holidays: list[str]

    def prompts_for_weekday(self, wkey: str) -> list[str]:
        """Return weekday prompt strings (stylistic part only)."""
        return self.by_weekday[wkey]

    def prompts_for_holidays(self) -> list[str]:
        """Return vacation-day prompt strings (stylistic part only)."""
        return self.holidays


def combine_with_base(base: str, day_prompt: str) -> str:
    """Prepend invariant Slack-avatar instructions to the day's prompt."""
    b = base.strip()
    d = day_prompt.strip()
    if not d:
        return b
    return f"{b}\n\n{d}"


def _parse_string_list(
    data: dict[str, object],
    key: str,
    *,
    label: str,
    min_items: int = 1,
) -> list[str]:
    if key not in data:
        msg = f"{label} missing key: {key}"
        raise KeyError(msg)
    val = data[key]
    is_str_list = isinstance(val, list) and all(
        isinstance(x, str) for x in val
    )
    if not is_str_list:
        msg = f"{label}['{key}'] must be a list of strings"
        raise TypeError(msg)
    strings = [s.strip() for s in val if s.strip()]
    if len(strings) < min_items:
        msg = f"{label}['{key}'] must contain at least one prompt"
        raise ValueError(msg)
    return strings


def load_prompts(path: Path) -> PromptsBundle:
    """Load prompts: base_prompt + weekday lists + holidays."""
    if not path.is_file():
        msg = f"Prompts file not found: {path}"
        raise FileNotFoundError(msg)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        msg = "prompts.json must be a JSON object"
        raise ValueError(msg)

    label = path.name
    allowed_keys = frozenset((BASE_PROMPT_KEY, HOLIDAYS_KEY, *WEEKDAY_KEYS))
    unknown = set(data.keys()) - allowed_keys
    if unknown:
        msg = f"{label} has unknown keys: {sorted(unknown)}"
        raise ValueError(msg)

    if BASE_PROMPT_KEY not in data:
        msg = f"{label} missing key: {BASE_PROMPT_KEY}"
        raise KeyError(msg)
    raw_base = data[BASE_PROMPT_KEY]
    if not isinstance(raw_base, str):
        msg = f"{label}['{BASE_PROMPT_KEY}'] must be a string"
        raise TypeError(msg)
    base = raw_base.strip()
    if not base:
        msg = f"{label}['{BASE_PROMPT_KEY}'] must be non-empty"
        raise ValueError(msg)

    holidays = _parse_string_list(data, HOLIDAYS_KEY, label=label)

    weekdays: dict[str, list[str]] = {}
    for key in WEEKDAY_KEYS:
        weekdays[key] = _parse_string_list(data, key, label=label)

    return PromptsBundle(
        base_prompt=base,
        by_weekday=weekdays,
        holidays=holidays,
    )
