"""Campaign detail page in plain language (P3 part 5, 161). Pure: rules dict (+ now) → sections of display text.
Money only through shared/payouts.py (describe / format_*), windows and status through payouts + campaign_status,
so the page never computes or words payouts itself. Fields a rules file doesn't have are simply left out."""

from __future__ import annotations

import re
from datetime import date, datetime

from shared import campaign_status, campaigns, payouts, rule_checks


def _day(d: date) -> str:
    return f"{d.day} {d.strftime('%b')}"


def _span(a: date, b: date) -> str:
    return f"{a.day}–{_day(b)}" if a.month == b.month else f"{_day(a)} – {_day(b)}"


def _topic(key: str) -> str:
    return key.replace("_", " ").strip().capitalize()


def _views(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def payout_lines(rules) -> list[str]:
    """The payout sentence first, then caps / limits / how views are counted, each a full sentence."""
    model = payouts.model_from_rules(rules)
    p, lim = rules.get("payout") or {}, rules.get("limits") or {}
    out = [payouts.describe(model)]
    if isinstance(model, payouts.FixedThreshold):
        out.append(f"A post earns once it reaches {_views(model.min_views)} views on its own platform (not summed across platforms).")
        if model.windows:
            out.append("Claim inside the week the clip was posted.")
    elif isinstance(model, payouts.PerBlock):
        out.append(f"Only full blocks of {_views(model.block_views)} views pay; views above "
                   f"{_views(model.max_counted_views)} don't count." if model.max_counted_views else
                   f"Only full blocks of {_views(model.block_views)} views pay.")
        if model.claims_per_post == 1:
            out.append("One claim per post" + (", on the views at the time you submit it." if p.get("views_counted") else "."))
    cap = lim.get("max_payout_per_creator_per_month")
    if cap:
        out.append(f"At most {payouts.format_idr(int(cap))} per creator per month.")
    if p.get("payment_methods"):
        out.append("Paid via " + ", ".join(p["payment_methods"]) + ".")
    return out


def weeks(rules, now: datetime) -> list[dict]:
    """Posting weeks (FixedThreshold windows): id, dates, state open|closed|upcoming, days left when open."""
    model = payouts.model_from_rules(rules)
    if not (isinstance(model, payouts.FixedThreshold) and model.windows):
        return []
    today = payouts._wib(now).date()
    out = []
    for w in model.windows:
        state = "open" if w.start <= today <= w.end else "closed" if today > w.end else "upcoming"
        out.append({"id": w.id, "dates": _span(w.start, w.end), "state": state,
                    "days_left": (w.end - today).days + 1 if state == "open" else None})
    return out


def period_text(rules) -> str | None:
    start, end = payouts.campaign_period(rules)
    until = ((rules.get("period") or {}).get("until") or "").strip()
    if start and end:
        return f"{_day(start)} – {_day(end)} {end.year}"
    if start:
        return f"From {_day(start)} {start.year}" + (f", until the {until}" if until else ", open-ended")
    if end:
        return f"Until {_day(end)} {end.year}"
    return None


def questions(rules) -> dict:
    """Open questions (unanswered, as the brief left them) and the admin's answers (keys admin_answers[_YYYY_MM_DD])."""
    open_q = [{"topic": _topic(k), "text": str(v)} for k, v in (rules.get("open_questions") or {}).items()]
    answers = []
    for key, block in rules.items():
        m = re.match(r"^admin_answers(?:_(\d{4})_(\d{2})_(\d{2}))?$", key)
        if m and isinstance(block, dict):
            when = f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m.group(1) else None
            answers += [{"topic": _topic(k), "text": str(v), "date": when} for k, v in block.items()]
    return {"open": open_q, "answered": answers}


def budget_lines(rules) -> list[str]:
    b = rules.get("budget") or {}
    cur = (b.get("currency") or "IDR").upper()
    out = []
    if b.get("total_per_month"):
        out.append(f"{payouts.format_money(b['total_per_month'], cur)} per month.")
    elif b.get("amount"):
        out.append(f"{payouts.format_money(b['amount'], cur)} in total.")
    if b.get("refills") and b.get("per_refill"):
        refill = ((rules.get("weeks") or {}).get("refill_time") or "").strip()
        out.append(f"Refilled {b['refills']}× ({payouts.format_money(b['per_refill'], cur)} each)"
                   + (f", every week at {refill} WIB" if refill else "") + "; first come, first served.")
    if not out and ((rules.get("period") or {}).get("until") or "").startswith("budget"):
        out.append("Total budget not stated; the campaign runs until it is used up.")
    return out


def build(rules, now: datetime) -> dict:
    p = rules.get("payout") or {}
    wm = campaigns.watermark(rules)
    return {
        "status": campaign_status.status(rules, now),
        "week": campaign_status.current_week(rules, now),
        "period": period_text(rules),
        "payout": payout_lines(rules),
        "platforms": [{"slug": s, "name": rule_checks.PLATFORM_LIMITS.get(s, (0, 0, s))[2]} for s in campaigns.platforms(rules)],
        "hashtags": campaigns.hashtags(rules),
        "watermark": {"required": bool(wm and wm["required"]), "name": wm and wm["asset_name"],
                      "has_asset": bool(wm and wm["asset_id"])} if wm else None,
        "weeks": weeks(rules, now),
        "content_rules": [r.get("text") or r.get("id") for r in campaigns.content_rules(rules)],
        "manual": [r.get("text") or r.get("id") for r in rules.get("manual_only") or []],
        "questions": questions(rules),
        "claim": {"form": p.get("claim_form"), "requires": p.get("claim_requires")} if p.get("claim_form") else None,
        "budget": budget_lines(rules),
    }
