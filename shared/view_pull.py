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

Instagram + Facebook (P5 parts 2+3, 199): one Meta token PER USER (user setting META_ACCESS_TOKEN, USER_ONLY: never
another user's), a Facebook Login user token with pages_show_list, pages_read_engagement, read_insights,
instagram_basic, instagram_manage_insights. The worker lists the user's Pages (`/me/accounts`, page tokens + linked
Instagram business accounts), finds each post among their recent media/reels and reads lifetime insights:

    instagram_shortcode(url)        # instagram.com/reel/<code> → matched against /{ig-user}/media shortcodes
    facebook_video_id(url, ext)     # facebook.com/reel/<id> → /{video}/video_insights with the Page's token
    ig_views(data) / fb_plays(data) # insights payload → int or None
    meta_error_kind(status, data)   # key | transient | request (same words as error_kind)
"""
import hashlib
import re
from datetime import datetime, timedelta
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

API_URL = "https://www.googleapis.com/youtube/v3/videos"
BATCH = 50
FAST_DAYS, STOP_DAYS = 14, 30
FAST_EVERY, SLOW_EVERY = timedelta(hours=6), timedelta(hours=24)
PLATFORMS = ("youtube", "instagram", "facebook")
META_PLATFORMS = ("instagram", "facebook")
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
    """'quota' (daily quota gone: stop until the Pacific reset) | 'key' (bad/expired/restricted key or the API not
    enabled: alert the admin) | 'request' (any other 4xx: our request, no alert) | 'transient' (5xx, per-100-s rate
    limits, network: just the next run). QA 189 Lows: rateLimitExceeded is transient; a 400 is 'key' only when it is."""
    err = (data or {}).get("error") or {}
    reasons = {e.get("reason") for e in err.get("errors") or [] if isinstance(e, dict)}
    message = str(err.get("message") or "").lower()
    if status == 403 and reasons & {"quotaExceeded", "dailyLimitExceeded"}:
        return "quota"
    if status in (400, 403) and (reasons & {"keyInvalid", "keyExpired", "accessNotConfigured", "ipRefererBlocked"}
                                 or "api key" in message):
        return "key"
    if status == 429 or reasons & {"rateLimitExceeded", "userRateLimitExceeded"} or status >= 500:
        return "transient"
    return "request" if 400 <= status < 500 else "transient"


# ---- Meta (Instagram + Facebook), 199 ----------------------------------------------------------------------------
GRAPH_URL = "https://graph.facebook.com/v23.0"
META_MAX_CALLS = 200            # per user per run; Meta's per-app limits are far above our volume
META_LIST_PAGES = 10            # ≤ 10 pages of 50 recent media/reels per account
META_LIST_SLACK = timedelta(days=2)   # the platform's timestamp vs. when the user marked it posted
FB_METRICS = ("fb_reels_total_plays", "blue_reels_play_count")   # first one present wins (UNCONFIRMED which matches
#                                                                  the public count: compare on the first run)
_IG_CODE = re.compile(r"instagram\.com/(?:[A-Za-z0-9_.]+/)?(?:reel|reels|p|tv)/([A-Za-z0-9_-]{5,})")
_FB_ID = re.compile(r"facebook\.com/(?:reel/|(?:[^/?#]+/)?videos/(?:[^/?#]+/)?|watch/?\?(?:[^#]*&)?v=)(\d{6,})")
_DIGITS = re.compile(r"^\d{6,}$")


def instagram_shortcode(url: Optional[str]) -> Optional[str]:
    m = _IG_CODE.search(url or "")
    return m.group(1) if m else None


def facebook_video_id(url: Optional[str], external_id: Optional[str] = None) -> Optional[str]:
    if external_id and _DIGITS.match(external_id.strip()):
        return external_id.strip()
    m = _FB_ID.search(url or "")
    return m.group(1) if m else None


def token_hash(token: str) -> str:
    """Fingerprint stored on view_pull_runs so a refused token is retried only after the user saves a new one."""
    return hashlib.sha256(token.encode()).hexdigest()[:16]


def _metric_value(entry: dict) -> Optional[int]:
    tv = entry.get("total_value")
    raw = tv.get("value") if isinstance(tv, dict) else None
    if raw is None:
        values = entry.get("values") or []
        raw = values[-1].get("value") if values and isinstance(values[-1], dict) else None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _metrics(data: Optional[dict]) -> dict:
    return {e.get("name"): _metric_value(e) for e in (data or {}).get("data") or [] if isinstance(e, dict)}


def ig_views(data: Optional[dict]) -> Optional[int]:
    return _metrics(data).get("views")


def fb_plays(data: Optional[dict]) -> Optional[int]:
    m = _metrics(data)
    return next((m[k] for k in FB_METRICS if m.get(k) is not None), None)


def meta_error_kind(status: int, data: Optional[dict], per_object: bool = False) -> str:
    """'key' (token expired/invalid, or a permission missing: tell the user) | 'transient' (rate limits, 5xx, Meta's
    temporary errors: next run) | 'request' (this object: not ours, metric unavailable…: an error on that post only).
    QA 199 Low 2: a permission error (10, 2xx) on a call about ONE media/Page/video is that object's problem
    (per_object=True → 'request'); only on the token-wide `/me/accounts` call does it mean the token lacks it."""
    err = (data or {}).get("error") or {}
    try:
        code = int(err.get("code"))
    except (TypeError, ValueError):
        code = None
    if code in (190, 102):
        return "key"
    if code == 10 or (code is not None and 200 <= code <= 299):
        return "request" if per_object else "key"
    if code in (1, 2, 4, 17, 32, 341, 368, 613) or (code is not None and 80001 <= code <= 80014) \
            or err.get("is_transient") or status == 429 or status >= 500:
        return "transient"
    return "request" if 400 <= status < 500 else "transient"
