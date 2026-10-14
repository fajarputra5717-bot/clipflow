"""Review page state from the payout rules (lane B, P4 task 6 filters). Pure; payouts.py is the ONE
source for windows/periods (main owns its posting-eligibility section), this only phrases them for the
Review header and decides which clips can no longer earn (badge + sorted last)."""

from __future__ import annotations

from datetime import datetime

from shared import payouts


def campaign_status(rules, now: datetime) -> dict:
    """{text, ended}: 'Week 2 · 6 days left' / '12 days left' / 'Open until the budget runs out' / 'Ended'."""
    model = payouts.model_from_rules(rules)
    today = payouts._wib(now).date()
    start, end = payouts.campaign_period(rules)
    if end and today > end:
        return {"text": "Ended", "ended": True}
    if start and today < start:
        return {"text": f"Starts {start.day} {start.strftime('%b')}", "ended": False}
    if isinstance(model, payouts.FixedThreshold) and model.windows:
        cur = next((w for w in model.windows if w.start <= today <= w.end), None)
        if cur:
            left = (cur.end - today).days + 1
            return {"text": f"Week {cur.id.lstrip('W')} · {left} day{'s' if left != 1 else ''} left", "ended": False}
        if today > model.windows[-1].end:
            return {"text": "All weeks closed", "ended": True}
        nxt = next(w for w in model.windows if w.start > today)
        return {"text": f"Between weeks · Week {nxt.id.lstrip('W')} starts {nxt.start.day} {nxt.start.strftime('%b')}",
                "ended": False}
    if end:
        left = (end - today).days + 1
        return {"text": f"{left} day{'s' if left != 1 else ''} left", "ended": False}
    return {"text": "Open until the budget runs out", "ended": False}


def earn_state(rules, model, posts, now: datetime):
    """None = the clip can still earn; else {code, label}: 'Campaign ended' (period over), or
    'Week closed' (FixedThreshold: every post of it went up in a week that has closed, or it is unposted
    and today is outside every week window, so posting now can't earn)."""
    probs = {p["code"] for p in payouts.window_problems(rules, model, now)}
    if "after_end" in probs:
        return {"code": "campaign_ended", "label": "Campaign ended"}
    if isinstance(model, payouts.FixedThreshold) and model.windows:
        posted = [p for p in posts or [] if p.get("posted_at")]
        if posted:
            def closed(p):
                w = payouts.window_for(model, p["posted_at"])
                return w is None or now >= w.closes_at()
            if all(closed(p) for p in posted):
                return {"code": "week_closed", "label": "Week closed"}
        elif "outside_window" in probs:
            return {"code": "week_closed", "label": "Week closed"}
    return None


# Review (owner 2026-10-14): a finished clip shows where it stands instead of a disabled Approve button.
PLATFORM_NAMES = {"tiktok": "TikTok", "instagram": "Instagram", "youtube": "YouTube", "facebook": "Facebook",
                  "threads": "Threads", "x": "X"}   # every posts.PLATFORM_HOSTS key
APPROVED = ("render_queued", "rendering", "completed")


def _when(dt: datetime, now: datetime) -> str:
    """WIB, short: 'Wed 17:00' within the coming week, else 'Wed 22 Oct 17:00'."""
    d, n = dt.astimezone(payouts.WIB), now.astimezone(payouts.WIB)
    days = (d.date() - n.date()).days
    return d.strftime("%a %H:%M") if 0 <= days < 7 else d.strftime("%a %-d %b %H:%M")


def finished_label(status: str, posts, now: datetime):
    """'Approved · Scheduled Wed 17:00' etc. for an approved clip (status in APPROVED), else None.
    posts = this clip's own clip_posts rows [{platform, status, scheduled_for, posted_at}]; dropped rows are ignored."""
    if status not in APPROVED:
        return None
    live = [p for p in (posts or []) if p.get("status") != "dropped"]
    posted = [p for p in live if p.get("status") in ("posted", "claimed", "paid")]
    planned = sorted((p for p in live if p.get("status") == "planned" and p.get("scheduled_for")),
                     key=lambda p: p["scheduled_for"])
    if posted:
        names = sorted({PLATFORM_NAMES.get(p.get("platform"), p.get("platform") or "?") for p in posted})
        out = "Posted on " + (names[0] if len(names) == 1 else f"{len(names)} platforms")
        nxt = planned[0]["scheduled_for"] if planned else None
        return out + (f" · next {_when(nxt, now)}" + (" (overdue)" if nxt < now else "") if nxt else "")   # QA Low 1
    if planned:
        nxt = planned[0]["scheduled_for"]
        return f"Approved · Scheduled {_when(nxt, now)}" + (" (overdue)" if nxt < now else "")
    return "Approved · Rendering final" if status != "completed" else "Approved · Not scheduled yet"
