"""Optional vacation calendar from JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

TIMEZONE_KEY = "timezone"
DATES_KEY = "dates"
ALLOWED_KEYS = frozenset((TIMEZONE_KEY, DATES_KEY))


@dataclass(frozen=True)
class VacationsConfig:
    """Personal vacation dates and the timezone used to interpret 'today'."""

    timezone: ZoneInfo
    dates: frozenset[date]


def load_vacations(path: Path) -> VacationsConfig | None:
    """Load vacation config; missing file returns None without error."""
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        msg = f"{path.name} must be a JSON object"
        raise ValueError(msg)

    unknown = set(data.keys()) - ALLOWED_KEYS
    if unknown:
        msg = f"{path.name} has unknown keys: {sorted(unknown)}"
        raise ValueError(msg)

    if TIMEZONE_KEY not in data:
        msg = f"{path.name} missing key: {TIMEZONE_KEY}"
        raise KeyError(msg)
    if DATES_KEY not in data:
        msg = f"{path.name} missing key: {DATES_KEY}"
        raise KeyError(msg)

    raw_tz = data[TIMEZONE_KEY]
    if not isinstance(raw_tz, str):
        msg = f"{path.name}['{TIMEZONE_KEY}'] must be a string"
        raise TypeError(msg)
    tz_name = raw_tz.strip()
    if not tz_name:
        msg = f"{path.name}['{TIMEZONE_KEY}'] must be non-empty"
        raise ValueError(msg)
    try:
        zone = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        msg = f"{path.name} has invalid IANA timezone {tz_name!r}"
        raise ValueError(msg) from exc

    raw_dates = data[DATES_KEY]
    if not isinstance(raw_dates, list):
        msg = f"{path.name}['{DATES_KEY}'] must be a list of strings"
        raise TypeError(msg)

    parsed: set[date] = set()
    for item in raw_dates:
        if not isinstance(item, str):
            msg = f"{path.name}['{DATES_KEY}'] must be a list of strings"
            raise TypeError(msg)
        text = item.strip()
        if not text:
            continue
        try:
            parsed.add(date.fromisoformat(text))
        except ValueError as exc:
            msg = (
                f"{path.name}['{DATES_KEY}'] entry {item!r} must be YYYY-MM-DD"
            )
            raise ValueError(msg) from exc

    return VacationsConfig(timezone=zone, dates=frozenset(parsed))


def is_vacation_today(config: VacationsConfig) -> bool:
    """True if today's calendar date in config.timezone is listed."""
    today = datetime.now(config.timezone).date()
    return today in config.dates
