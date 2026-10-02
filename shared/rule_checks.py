"""
Campaign rule chips (P1, 109): what a campaign clip must pass before Approve.
Pure: rules dict (shared/campaigns) + candidate row dict in, chips out. Used by
main.py for the job-detail payload AND the approve gate, so UI and API agree.

Chip: {id, ok, blocking, label, detail, fix}. blocking chips gate Approve;
warning chips (content safety) never do — the user decides.
"""

import re

from shared import campaigns

# Duration limits in seconds per platform slug (rules files' "platforms"), from Lane B's
# docs/research/publishing-apis.md (read 2026-10-02). TikTok's API limit is unconfirmed
# (300 s vs 10 min): the conservative 300. X: the long-standing 140 s for standard accounts.
PLATFORM_LIMITS = {
    "facebook": (3, 90, "Facebook Reels"),
    "instagram": (3, 900, "Instagram Reels"),
    "youtube": (1, 180, "YouTube Shorts"),
    "tiktok": (3, 300, "TikTok"),
    "threads": (1, 300, "Threads"),
    "x": (1, 140, "X"),
}

HASHTAG_RE = re.compile(r"#\w+", re.UNICODE)


def _duration(c):
    try:
        return max(0.0, float(c.get("end_time") or 0) - float(c.get("start_time") or 0))
    except (TypeError, ValueError):
        return 0.0


def hashtags_ok(description, required):
    """The description ENDS with the required hashtags, in order, together, nothing after."""
    if not required:
        return True
    text = (description or "").strip()
    return text.endswith(" ".join(required)) and HASHTAG_RE.findall(text)[-len(required):] == list(required)


def check(rules, c):
    """Chips for one candidate of a campaign job; [] when there is no campaign."""
    if not rules:
        return []
    chips = []

    dur = _duration(c)
    bad = []
    for slug in campaigns.platforms(rules):
        lo, hi, name = PLATFORM_LIMITS.get(slug, (None, None, slug))
        if lo is not None and not lo <= dur <= hi:
            bad.append(f"{name} ({lo}–{hi} s)")
    chips.append({
        "id": "length", "ok": not bad, "blocking": True,
        "label": f"Length {round(dur)} s" if not bad else f"Length {round(dur)} s: too long for " + ", ".join(bad),
        "detail": "Platform limits from the campaign's platforms.",
        "fix": None,  # trimming arrives with the P4 timeline
    })

    required = campaigns.hashtags(rules)
    if required:
        ok = hashtags_ok(c.get("description"), required)
        chips.append({
            "id": "hashtags", "ok": ok, "blocking": True,
            "label": "Hashtags" if ok else "Hashtags missing or out of order",
            "detail": "Ends with: " + " ".join(required),
            "fix": None if ok else "hashtags",
        })

    wm = campaigns.watermark(rules)
    if wm and wm.get("required"):
        warn = next((w for w in (c.get("render_warnings") or []) if w.get("code") == "campaign_watermark"), None)
        chips.append({
            "id": "watermark", "ok": warn is None, "blocking": True,
            "label": "Watermark" if warn is None else "Campaign watermark missing",
            "detail": (warn or {}).get("message") or f"{wm.get('asset_name') or 'Campaign watermark'} burned in.",
            "fix": None,
        })

    safety = c.get("safety_check")
    if isinstance(safety, dict):
        flags = safety.get("flags") or []
        if safety.get("dismissed"):
            flags = []
        chips.append({
            "id": "safety", "ok": not flags, "blocking": False,
            "label": "Content check" if not flags else f"Content check: {len(flags)} possible issue{'s' if len(flags) != 1 else ''}",
            "detail": "; ".join(f"[{f.get('rule')}] “{f.get('quote', '')}”: {f.get('reason', '')}" for f in flags)
                      or ("Dismissed by you." if safety.get("dismissed") else "No campaign content rule looks broken."),
            "fix": "dismiss" if flags else None,
        })
    return chips


def blocking_failures(chips):
    return [ch for ch in chips if ch["blocking"] and not ch["ok"]]
