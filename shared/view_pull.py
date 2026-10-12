"""Automatic view pulling (P5 part 1): YouTube posts' view counts via YouTube Data API v3 `videos.list`
(`part=statistics`, API key only: setting YOUTUBE_API_KEY, admin-only). Pure rules; the worker does the I/O.

    vid = youtube_id(post["url"], post.get("external_id"))     # 11-char id or None
    due(post, now)                                             # cadence: 6 h < 14 days old, daily until 30, then stop
    for ids in batches(sorted(due_ids)): …                    # ≤ 50 ids per call, 1 quota unit each
    counts = parse_counts(resp_json)                           # {id: views}; a missing id = deleted/private

Quota: Google gives 10,000 units/day (reset midnight Pacific) shared by every non-upload call; view pulls spend at
most VIEW_PULL_DAILY_UNITS of it (default 1000) so uploads/other reads keep headroom. A 403 quotaExceeded stops pulls
until the next Pacific midnight. Writes look like a manual entry (clip_posts.views + views_at, a clip_post_views row)
with source 'auto', so claim advice (24 h growth) and Track read them unchanged.
"""
import re
from datetime import datetime, timedelta
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

API_URL = "https://www.googleapis.com/youtube/v3/videos"
BATCH = 50
FAST_DAYS, STOP_DAYS = 14, 30
FAST_EVERY, SLOW_EVERY = timedelta(hours=6), timedelta(hours=24)
PLATFORMS = ("youtube",)
PACIFIC = ZoneInfo("America/Los_Angeles")
_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_URL_ID = re.compile(r"(?:youtube\.com/(?:shorts/|watch\?(?:[^#]*&)?v=|live/|embed/)|youtu\.be/)([A-Za-z0-9_-]{11})")


def youtube_id(url: Optional[str], external_id: Optional[str] = None) -> Optional[str]:
    if external_id and _ID.match(external_id.strip()):
        return external_id.strip()
    m = _URL_ID.search(url or "")
    return m.group(1) if m else None


def due(post: dict, now: datetime) -> bool:
    """posted_at < 14 days ago: every 6 h; < 30 days: every 24 h; older (or never posted): never."""
    posted = post.get("posted_at")
    if not posted or post.get("platform") not in PLATFORMS:
        return False
    age = now - posted
    if age >= timedelta(days=STOP_DAYS) or age < timedelta(0):
        return False
    last = post.get("views_pulled_at")
    every = FAST_EVERY if age < timedelta(days=FAST_DAYS) else SLOW_EVERY
    return last is None or now - last >= every - timedelta(minutes=5)   # 5 min slack: the poll isn't exact


def batches(ids: Iterable[str], size: int = BATCH) -> list[list[str]]:
    ids = list(dict.fromkeys(ids))
    return [ids[i:i + size] for i in range(0, len(ids), size)]


def parse_counts(data: dict) -> dict[str, int]:
    out = {}
    for item in (data or {}).get("items") or []:
        try:
            out[item["id"]] = int(item["statistics"]["viewCount"])
        except (KeyError, TypeError, ValueError):
            continue   # hidden counts / no statistics: treated like not returned
    return out


def quota_day_start(now: datetime) -> datetime:
    """The current quota day's start (midnight Pacific), as an aware datetime."""
    local = now.astimezone(PACIFIC)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def next_quota_reset(now: datetime) -> datetime:
    start = quota_day_start(now)
    return (start + timedelta(days=1, hours=2)).replace(hour=0)   # +2 h then snap: safe across DST changes


def error_kind(status: int, data: Optional[dict]) -> str:
    """'quota' (stop until reset) | 'key' (bad/missing key: alert admin, retry later) | 'transient'."""
    reasons = {e.get("reason") for e in ((data or {}).get("error") or {}).get("errors") or [] if isinstance(e, dict)}
    if status == 403 and reasons & {"quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"}:
        return "quota"
    if status in (400, 403) and (reasons & {"keyInvalid", "accessNotConfigured", "keyExpired", "forbidden", "ipRefererBlocked"}
                                 or status == 400):
        return "key"
    return "transient"
