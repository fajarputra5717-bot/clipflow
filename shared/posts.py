"""
clip_posts rules (P2 part 2, 129): one row per clip per platform post. The
record the manual "Mark posted" flow writes today and the future auto-poster
(P5) and view tracker will write to, so every writer validates through here.

Lifecycle:  planned → posted → claimed → paid,  and any non-paid state → dropped.
            dropped → planned (re-plan). paid is final.
Money: paid_rp is whole Rupiah (IDR). Payout amounts are computed by Lane B's
shared/payouts.py once it is merged (P3); nothing here does payout math.
"""

import re as _re
import unicodedata as _ud
from urllib.parse import urlsplit

STATUSES = ("planned", "posted", "claimed", "paid", "dropped")

TRANSITIONS = {
    "planned": {"posted", "dropped"},
    "posted": {"claimed", "dropped"},
    "claimed": {"paid", "dropped"},
    "paid": set(),
    "dropped": {"planned"},
}

SOURCES = ("manual", "auto")

# Hosts a post URL may live on, per rule_checks.PLATFORM_LIMITS key.
PLATFORM_HOSTS = {
    "tiktok": ("tiktok.com",),
    "instagram": ("instagram.com",),
    "youtube": ("youtube.com", "youtu.be"),
    "facebook": ("facebook.com", "fb.watch"),
    "threads": ("threads.net", "threads.com"),
    "x": ("x.com", "twitter.com"),
}


def transition_problem(current: str, new: str) -> str | None:
    if new not in STATUSES:
        return f"Unknown status {new!r}"
    if new == current:
        return None
    if new not in TRANSITIONS.get(current, set()):
        return f"A {current} post can't become {new}"
    return None


def url_problem(platform: str, url: str | None) -> str | None:
    """https link on the platform's own domain (subdomains allowed)."""
    if not url:
        return None
    url = url.strip()
    try:
        parts = urlsplit(url)
    except ValueError:
        return "That doesn't look like a link"
    if parts.scheme != "https" or not parts.hostname:
        return "Use the https:// link of the post"
    host = parts.hostname.lower()
    allowed = PLATFORM_HOSTS.get(platform, ())
    if not any(host == h or host.endswith("." + h) for h in allowed):
        return f"That link isn't on {', '.join(allowed) or platform}"
    if len(url) > 500:
        return "Link is too long"
    return None


def needs(status: str) -> list[str]:
    """Fields a post must have once it reaches `status`."""
    if status in ("posted", "claimed", "paid"):
        return ["account_id", "url", "posted_at"]
    return []


def rp_problem(value) -> str | None:
    if value is None:
        return None
    try:
        v = int(value)
    except (TypeError, ValueError):
        return "Amount must be whole Rupiah"
    if v < 0 or v > 1_000_000_000:
        return "Amount must be between Rp 0 and Rp 1.000.000.000"
    return None


# ---------- Publish queue (P2 part 3, 130) ----------


# Caption (post text) and title limits per platform, characters. Lane B's research doc
# (docs/research/publishing-apis.md) is the source when it lands; these are the
# platforms' published maxima as of 2026-10.
CAPTION_LIMITS = {"tiktok": 2200, "instagram": 2200, "youtube": 5000, "facebook": 2200, "threads": 500, "x": 280}
TITLE_LIMITS = {"youtube": 100}

# jobs.platform (Analyze form) → PLATFORM_LIMITS key, for clips without a campaign.
JOB_PLATFORM = {"youtube_shorts": "youtube", "instagram_reels": "instagram", "tiktok": "tiktok"}


def trim_caption(body: str, hashtags: list, limit: int) -> tuple[str, bool]:
    """Caption = body, blank line, hashtags in their exact order. When it is too long,
    the BODY is shortened (word boundary, "…"); hashtags are never cut or reordered.
    Returns (caption, trimmed)."""
    tags = " ".join(hashtags or [])
    body = (body or "").strip()
    sep = "\n\n" if body and tags else ""
    full = f"{body}{sep}{tags}"
    if len(full) <= limit:
        return full, False
    room = limit - len(tags) - len(sep) - 1  # 1 for "…"
    if room <= 0:
        return tags[:limit], True
    cut = body[:room]
    if " " in cut[room // 2:]:
        cut = cut[: cut.rfind(" ")]
    return f"{cut.rstrip(' ,.;:')}…{sep}{tags}", True


def trim_title(title: str, platform: str) -> str:
    limit = TITLE_LIMITS.get(platform)
    title = (title or "").strip()
    if limit and len(title) > limit:
        return title[: limit - 1].rstrip() + "…"
    return title


def slug(text: str, max_len: int = 40) -> str:
    t = _ud.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    t = _re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return (t[:max_len].rstrip("-")) or "clip"


def download_name(campaign: str | None, platform: str | None, title: str) -> str:
    """campaign_platform_slug.mp4 (no campaign → "clip"; no platform → campaign_slug.mp4, the clip card's download)."""
    mid = f"_{platform}" if platform else ""
    return f"{slug(campaign or 'clip', 30)}{mid}_{slug(title)}.mp4"


def clip_platforms(rules, job_platform: str | None) -> list:
    """Platforms a finished clip is posted to: the campaign's (known ones), else the job's Analyze platform."""
    from shared import campaigns, rule_checks
    if rules:
        return [p for p in campaigns.platforms(rules) if p in rule_checks.PLATFORM_LIMITS]
    return [JOB_PLATFORM.get(job_platform or "", "youtube")]
