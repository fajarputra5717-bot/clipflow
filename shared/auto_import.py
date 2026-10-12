"""Auto-import (P3 part 7): pure rules that turn shared/source_watch's "what is new" into per-user imports.

Flow: a user switches a campaign source channel on (`source_watches`, one row per user × campaign × channel, with
`enabled_at`) → the worker checks each watched channel once per AUTO_IMPORT_INTERVAL_MIN (`source_channels` = the
shared check queue, one row per channel, no user data, like `source_videos`) → for every enabled watch of that
channel each new video becomes a `source_imports` row: `found` (the backend's import loop turns it into a job via the
same create_job path as the Analyze form → `imported`, job defaults from the campaign) or `skipped` + reason.
Dedupe by URL per user: UNIQUE (user_id, url) + an existing job of that user with the URL.

    key = channel_key("@FandraOcto")            # "https://www.youtube.com/@fandraocto"
    reason = skip_reason(item, rules, enabled_at=…, now=…, min_seconds=300, stale=False)   # None = import it
"""
from datetime import datetime, timedelta
from typing import Optional

from shared import campaign_status, payouts, source_watch

# A stream that started before the switch went on but finished after it still counts.
ENABLED_SLACK = timedelta(hours=12)
# A channel whose last good check is older than this has a stale seen-list: everything it reports as "new" may be
# days old, so a video without an upload time (past the RSS window) is skipped instead of imported.
STALE_AFTER = timedelta(hours=24)
STATUSES = ("found", "imported", "skipped", "failed")


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


def skip_reason(item: dict, rules: dict, *, enabled_at: datetime, now: datetime, min_seconds: int,
                stale: bool = False) -> Optional[str]:
    """Why a new video of a watched channel is NOT imported for this watch; None = import it."""
    code = campaign_status.status(rules, now)["code"]
    if code == "paused":
        return "Campaign paused"
    if code == "ended":
        return "Campaign ended"
    duration = item.get("duration")
    if duration is not None and duration < min_seconds:
        return f"Under {max(1, round(min_seconds / 60))} min"
    published = parse_time(item.get("published_at"))
    if published is None:
        return "Older than the watch" if stale else None
    if published < enabled_at - ENABLED_SLACK:
        return "Uploaded before auto-import was on"
    start, _ = payouts.campaign_period(rules)
    if start and payouts._wib(published).date() < start:
        return "Uploaded before the campaign started"
    return None
