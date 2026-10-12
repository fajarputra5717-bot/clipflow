"""Auto-import (P3 part 7): pure rules that turn shared/source_watch's "what is new" into per-user imports.

Flow: a user switches a campaign source channel on (`source_watches`, one row per user × campaign × channel, with
`enabled_at`) → the worker checks each watched channel once per AUTO_IMPORT_INTERVAL_MIN (`source_channels` = the
shared check queue, one row per channel, no user data, like `source_videos`) → for every enabled watch of that
channel each new video becomes a `source_imports` row: `found` (the backend's import loop turns it into a job via the
same create_job path as the Analyze form → `imported`, job defaults from the campaign) or `skipped` + reason.
Dedupe by URL per user: UNIQUE (user_id, url) + an existing job of that user with the URL.

    key = channel_key("@FandraOcto")            # "https://www.youtube.com/@fandraocto"
    g = normalize_guardrails(watch["guardrails"])  # per watch (user × campaign × channel), defaults merged
    reason = skip_reason(item, rules, enabled_at=…, now=…, guard=g, stale=False)   # None = import it

Guardrails (184): max new jobs per day (WIB, per user × channel; counted by the worker), duration window, title
keywords (include = at least one, exclude = none; case-insensitive substrings), pause while the disk has < X GB free
(the backend keeps the row `found` and retries), a Telegram note per imported job (the user's own chat).
"""
from datetime import datetime, timedelta
from typing import Optional

from shared import campaign_status, payouts, source_watch

# A stream that started before the switch went on but finished after it still counts.
ENABLED_SLACK = timedelta(hours=12)
# A channel whose last good check is older than this has a stale seen-list (only changes the skip reason of a video
# without an upload time: "Older than the watch" instead of "No upload time").
STALE_AFTER = timedelta(hours=24)
STATUSES = ("found", "imported", "skipped", "failed")
# 187: skip reasons the user may override ("Found, not imported: confirm?" on the Campaign page) — the rules couldn't
# vouch for the video, they didn't rule it out. Confirmed rows go back to `found` with reason CONFIRMED.
CONFIRMABLE = ("No upload time", "Older than the watch", "Unknown length")
CONFIRMED = "Confirmed by you"
GUARD_DEFAULTS = {"max_per_day": 2, "min_minutes": 5, "max_minutes": 240, "include": [], "exclude": [],
                  "pause_below_gb": None, "telegram_note": True}
MAX_KEYWORDS, MAX_KEYWORD_LEN = 10, 40


def _int(v, name, lo, hi):
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a whole number")
    if not lo <= n <= hi:
        raise ValueError(f"{name} must be {lo}–{hi}")
    return n


def _words(v, name):
    if isinstance(v, str):
        v = v.split(",")
    if not isinstance(v, (list, tuple)):
        raise ValueError(f"{name} must be a list of words")
    out = []
    for w in v:
        w = " ".join(str(w).split()).lower()
        if not w or w in out:
            continue
        if len(w) > MAX_KEYWORD_LEN:
            raise ValueError(f"{name}: '{w[:20]}…' is longer than {MAX_KEYWORD_LEN} characters")
        out.append(w)
    if len(out) > MAX_KEYWORDS:
        raise ValueError(f"{name}: at most {MAX_KEYWORDS} words")
    return out


def normalize_guardrails(raw, base: Optional[dict] = None) -> dict:
    """Merge `raw` over `base` (else the defaults) and validate. Unknown keys are dropped; raises ValueError."""
    g = dict(GUARD_DEFAULTS)
    g.update({k: v for k, v in (base or {}).items() if k in GUARD_DEFAULTS})
    raw = {k: v for k, v in (raw or {}).items() if k in GUARD_DEFAULTS}
    g.update(raw)
    g["max_per_day"] = _int(g["max_per_day"], "Max new jobs per day", 1, 20)
    g["min_minutes"] = _int(g["min_minutes"], "Shortest video (min)", 0, 600)
    g["max_minutes"] = _int(g["max_minutes"], "Longest video (min)", 1, 1440)
    if g["max_minutes"] <= g["min_minutes"]:
        raise ValueError("Longest video must be longer than the shortest")
    g["include"] = _words(g["include"], "Only titles with")
    g["exclude"] = _words(g["exclude"], "Skip titles with")
    if g["pause_below_gb"] in (None, "", 0, "0"):
        g["pause_below_gb"] = None
    else:
        g["pause_below_gb"] = _int(g["pause_below_gb"], "Pause below (GB)", 1, 10000)
    g["telegram_note"] = bool(g["telegram_note"]) if not isinstance(g["telegram_note"], str) else g["telegram_note"].lower() in ("1", "true", "on", "yes")
    return g


def _minutes_fmt(m: int) -> str:
    return f"{m // 60} h" if m >= 60 and m % 60 == 0 else (f"{m // 60} h {m % 60} min" if m >= 60 else f"{m} min")


def describe(g: dict) -> str:
    """One plain line for the UI: "Max 2 a day · 5 min–4 h · only: ranked · pauses below 50 GB · Telegram note"."""
    parts = [f"Max {g['max_per_day']} a day", f"{_minutes_fmt(g['min_minutes'])}–{_minutes_fmt(g['max_minutes'])}"]
    if g["include"]:
        parts.append("only: " + ", ".join(g["include"]))
    if g["exclude"]:
        parts.append("not: " + ", ".join(g["exclude"]))
    if g["pause_below_gb"]:
        parts.append(f"pauses below {g['pause_below_gb']} GB free")
    parts.append("Telegram note" if g["telegram_note"] else "no Telegram note")
    return " · ".join(parts)


def guard_reason(item: dict, g: dict) -> Optional[str]:
    """The per-watch filters that only need the video itself (the daily cap and disk pause need state)."""
    duration = item.get("duration")
    if duration is None:
        return "Unknown length"   # QA P3 Low: an unknown length can't be checked against the window, so not imported
    if duration < g["min_minutes"] * 60:
        return f"Under {_minutes_fmt(g['min_minutes'])}"
    if duration > g["max_minutes"] * 60:
        return f"Over {_minutes_fmt(g['max_minutes'])}"
    title = (item.get("title") or "").lower()
    if g["include"] and not any(w in title for w in g["include"]):
        return "Title has none of: " + ", ".join(g["include"])
    hit = next((w for w in g["exclude"] if w in title), None)
    if hit:
        return f"Title has '{hit}'"
    return None


def channel_key(channel: str) -> str:
    """The one spelling of a channel used in the DB (handles are case-insensitive on YouTube)."""
    base = source_watch.channel_base(channel)
    head, _, tail = base.rpartition("/")
    return f"{head}/{tail.lower()}" if tail.startswith("@") else base


def channel_label(key: str) -> str:
    tail = key.rstrip("/").rpartition("/")[2]
    return tail if tail.startswith("@") else key


def watchable(rules: Optional[dict]) -> list[dict]:
    """The campaign's YouTube source channels that can be watched: [{channel (key), label, content}]."""
    out, seen = [], set()
    for s in (rules or {}).get("sources") or []:
        if (s.get("platform") or "youtube") != "youtube" or not s.get("channel"):
            continue
        try:
            key = channel_key(str(s["channel"]))
        except source_watch.SourceWatchError:
            continue
        if key not in seen:
            seen.add(key)
            out.append({"channel": key, "label": channel_label(key), "content": s.get("content") or ""})
    return out


def parse_time(ts) -> Optional[datetime]:
    if isinstance(ts, datetime):
        return ts
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00")) if ts else None
    except ValueError:
        return None
    return dt if dt is None or dt.tzinfo else None


def skip_reason(item: dict, rules: dict, *, enabled_at: datetime, now: datetime, guard: Optional[dict] = None,
                stale: bool = False) -> Optional[str]:
    """Why a new video of a watched channel is NOT imported for this watch; None = import it."""
    code = campaign_status.status(rules, now)["code"]
    if code == "paused":
        return "Campaign paused"
    if code == "ended":
        return "Campaign ended"
    why = guard_reason(item, guard or normalize_guardrails(None))
    if why:
        return why
    published = parse_time(item.get("published_at"))
    if published is None:
        # QA P3 Medium: no upload time (past the RSS window or a feed failure) = can't prove it's new → skipped,
        # listed in Recent imports with the reason (import it from Analyze if wanted). Never imported blind.
        return "Older than the watch" if stale else "No upload time"
    if published < enabled_at - ENABLED_SLACK:
        return "Uploaded before auto-import was on"
    start, _ = payouts.campaign_period(rules)
    if start and payouts._wib(published).date() < start:
        return "Uploaded before the campaign started"
    return None
