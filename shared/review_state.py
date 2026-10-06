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
