"""
Posting schedule (P2.5 S1): suggested posting times per platform, per user.

POSTING_TIMES (user setting) = JSON {platform: ["HH:MM", …]} in WIB (Asia/Jakarta, UTC+7, no DST), keys =
rule_checks.PLATFORM_LIMITS names. Defaults live in shared/settings.DEFAULT_SETTINGS (owner-approved
2026-10-07). Pure helpers, no DB: callers pass what is already taken. Datetimes in and out are aware; slots
come back in UTC (stored as TIMESTAMPTZ), shown in WIB.
"""

import json
import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable, Optional

from shared import payouts, rule_checks

WIB = payouts.WIB
MAX_TIMES_PER_PLATFORM = 8
_HHMM = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def normalize_posting_times(value) -> dict:
    """Validated {platform: sorted unique "HH:MM"}; raises ValueError (message is user-facing).
    Accepts the JSON string or a dict. A platform may have [] (no suggestions)."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            raise ValueError("Posting times must be JSON like {\"tiktok\": [\"19:00\"]}")
    if not isinstance(value, dict):
        raise ValueError("Posting times must be an object of platform → list of times")
    out = {}
    for plat, times in value.items():
        if plat not in rule_checks.PLATFORM_LIMITS:
            raise ValueError(f"Unknown platform '{plat}'")
        if not isinstance(times, list):
            raise ValueError(f"{rule_checks.PLATFORM_LIMITS[plat][2]}: times must be a list")
        clean = set()
        for t in times:
            m = _HHMM.match(str(t).strip())
            if not m:
                raise ValueError(f"{rule_checks.PLATFORM_LIMITS[plat][2]}: '{t}' is not a time (HH:MM, 24 h)")
            clean.add(f"{int(m.group(1)):02d}:{m.group(2)}")
        if len(clean) > MAX_TIMES_PER_PLATFORM:
            raise ValueError(f"{rule_checks.PLATFORM_LIMITS[plat][2]}: at most {MAX_TIMES_PER_PLATFORM} times")
        out[plat] = sorted(clean)
    return out


def parse_posting_times(value, fallback=None) -> dict:
    """Lenient read of a stored value: invalid → fallback (the defaults) → {}."""
    for v in (value, fallback):
        if v in (None, ""):
            continue
        try:
            return normalize_posting_times(v)
        except ValueError:
            continue
    return {}


def _at(day: date, hhmm: str) -> datetime:
    h, m = map(int, hhmm.split(":"))
    return datetime.combine(day, time(h, m), WIB)


def _minute(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(second=0, microsecond=0)


def next_slots(times: dict, platform: str, after: datetime, taken: Iterable[datetime] = (), *,
               n: int = 3, rules: Optional[dict] = None, days: int = 14) -> list[datetime]:
    """The next `n` suggested slots (UTC) for `platform` strictly after `after`, skipping slots already
    `taken` (this user's planned/posted times on that account, same minute) and, with campaign `rules`,
    slots outside its posting window (period + week windows, payouts.window_problems). Looks `days` ahead."""
    if after.tzinfo is None:
        raise ValueError("after must be timezone-aware")
    daily = times.get(platform) or []
    if not daily:
        return []
    busy = {_minute(t) for t in taken if t}
    model = payouts.model_from_rules(rules) if rules else None
    first = after.astimezone(WIB).date()
    out = []
    for d in range(days + 1):
        day = first + timedelta(days=d)
        for hhmm in daily:
            slot = _at(day, hhmm)
            if slot <= after or _minute(slot) in busy:
                continue
            if rules and payouts.window_problems(rules, model, slot):
                continue
            out.append(slot.astimezone(timezone.utc))
            if len(out) >= n:
                return out
    return out
