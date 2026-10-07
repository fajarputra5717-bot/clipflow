"""Campaign status engine (P3 part 2, 158). Pure; windows and periods come from shared/payouts.py only, the
phrasing of the week/days line from shared/review_state.campaign_status (Lane B), so Review, the Campaign step
and the clip labels say the same thing.

status(rules, now)       → {code active|ending_soon|ended|paused, label, detail, last_day, days_left}
    paused   the campaign row's flag (rules["paused"]) — wins over everything
    ended    today (WIB) is past the last POSTING day: the period end or the last week window's end, whichever
             is earlier (IME: W4 ends 28 Oct → 29–31 Oct are "Ended" for posting even though October isn't over)
    ending_soon  ≤ ENDING_SOON_DAYS posting days left, today included (IME 26 Oct → 3)
    active   otherwise (also before the start: detail says "Starts …"); open-ended campaigns (Fandra) stay active
current_week(rules, now) → {id, start, end, days_left} of the open week window, or None.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from shared import payouts, review_state

ENDING_SOON_DAYS = 3
LABELS = {"active": "Active", "ending_soon": "Ending soon", "ended": "Ended", "paused": "Paused"}


def last_posting_day(rules) -> Optional[date]:
    _, end = payouts.campaign_period(rules)
    model = payouts.model_from_rules(rules)
    week_end = model.windows[-1].end if isinstance(model, payouts.FixedThreshold) and model.windows else None
    days = [d for d in (end, week_end) if d]
    return min(days) if days else None


def current_week(rules, now: datetime) -> Optional[dict]:
    model = payouts.model_from_rules(rules)
    if not (isinstance(model, payouts.FixedThreshold) and model.windows):
        return None
    w = payouts.window_for(model, now)
    if not w:
        return None
    today = payouts._wib(now).date()
    return {"id": w.id, "start": w.start.isoformat(), "end": w.end.isoformat(), "days_left": (w.end - today).days + 1}


def status(rules, now: datetime) -> dict:
    today = payouts._wib(now).date()
    last = last_posting_day(rules)
    left = (last - today).days + 1 if last else None
    detail = review_state.campaign_status(rules, now)["text"]
    if detail == "Open until the budget runs out" and "budget" not in str((rules.get("period") or {}).get("until") or ""):
        detail = "No end date set"   # the rules don't say the budget ends it (e.g. a pilot with TBD period)
    if rules.get("paused"):
        code = "paused"
    elif last and today > last:
        code, detail, left = "ended", f"Ended {last.day} {last.strftime('%b')}", 0
    elif left is not None and left <= ENDING_SOON_DAYS:
        code = "ending_soon"
    else:
        code = "active"
    return {"code": code, "label": LABELS[code], "detail": detail,
            "last_day": last.isoformat() if last else None, "days_left": left}


def clip_labels(rules, posts, now: datetime) -> dict:
    """P3 part 6 (162): what Review, Editor and Publish show for one clip of this campaign.
    earn    Lane B's review_state.earn_state: {code week_closed|campaign_ended, label} or None (can still earn)
    expired the campaign's posting is over (status 'ended'): the clip leaves the active queues for a collapsed
            "Expired" group. Nothing is deleted. posts = [{posted_at, ...}] of this clip (the user's own)."""
    if not rules:
        return {"earn": None, "expired": False}
    model = payouts.model_from_rules(rules)
    expired = status(rules, now)["code"] == "ended"
    earn = {"code": "campaign_ended", "label": "Campaign ended"} if expired else \
        review_state.earn_state(rules, model, posts or [], now)   # ended = past the last posting day (IME after W4)
    return {"earn": earn, "expired": expired}
