"""
clip_posts rules (P2 part 2, 129): one row per clip per platform post. The
record the manual "Mark posted" flow writes today and the future auto-poster
(P5) and view tracker will write to, so every writer validates through here.

Lifecycle:  planned → posted → claimed → paid,  and any non-paid state → dropped.
            dropped → planned (re-plan). paid is final.
Money: paid_rp is whole Rupiah (IDR). Payout amounts are computed by Lane B's
shared/payouts.py once it is merged (P3); nothing here does payout math.
"""

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
