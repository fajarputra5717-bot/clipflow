"""Track dashboard (P3 part 8, 181): one user's posts → tiles, per-campaign / per-platform breakdown, top clips.

Pure (no DB): the backend passes the caller's own clip_posts rows (posted / claimed / paid) and the campaign rules.
Every amount comes from shared/payouts.py and reaches the UI pre-formatted (`*_fmt`); non-IDR campaigns show
"$12.40 (~Rp 204.600)" and count in IDR totals at the payouts rate (a currency without a rate is skipped and listed).

Per post: paid → paid_rp; claimed → expected_rp (stored at claim); posted → what it would pay now
(payouts.payout_for at its latest views). "At cap" = the post already earns the campaign's max per post.
"""

from __future__ import annotations

from typing import Callable, Optional

from shared import payouts, rule_checks

LIVE = ("posted", "claimed", "paid")
TOP_N = 10


def fmt_views(n) -> str:
    return f"{int(n or 0):,}".replace(",", ".")


def _platform_name(slug: str) -> str:
    return rule_checks.PLATFORM_LIMITS.get(slug, (0, 0, slug))[2]


def _post_money(post: dict, model) -> tuple:
    """(amount, currency, state) for one post; amount None = unknown."""
    status = post.get("status")
    if status == "paid" and post.get("paid_rp") is not None:
        return int(post["paid_rp"]), "IDR", "paid"
    if status == "claimed" and post.get("expected_rp") is not None:
        return int(post["expected_rp"]), "IDR", "claimed"
    if model is None:
        return None, "IDR", "unknown"
    amount = payouts.payout_for(model, int(post.get("views") or 0))
    return amount, getattr(model, "currency", "IDR") or "IDR", "estimate"


def _at_cap(post: dict, model) -> bool:
    if model is None or post.get("status") == "paid":
        return False
    cap = payouts.max_payout(model)
    now = payouts.payout_for(model, int(post.get("views") or 0))
    return cap is not None and now is not None and now >= cap


def build(posts: list[dict], rules_for: Callable[[str], Optional[dict]], **rate) -> dict:
    """posts: the user's clip_posts rows (any status; only posted/claimed/paid count). rules_for(slug) → rules."""
    models, names = {}, {}

    def model_of(slug):
        if not slug:
            return None
        if slug not in models:
            rules = rules_for(slug)
            models[slug] = payouts.model_from_rules(rules) if rules else None
            names[slug] = (rules or {}).get("name") or slug
        return models[slug]

    live = [p for p in posts if p.get("status") in LIVE]
    rows, skipped = [], []
    for p in live:
        m = model_of(p.get("campaign"))
        amount, cur, state = _post_money(p, m)
        idr = payouts.to_idr(amount, cur, **rate)
        if amount is not None and idr is None and cur not in skipped:
            skipped.append(cur)
        rows.append({**p, "_amount": amount, "_cur": cur, "_state": state, "_idr": idr or 0, "_cap": _at_cap(p, m)})

    def group(key, label):
        out = {}
        for r in rows:
            k = key(r) or ""
            g = out.setdefault(k, {"key": k, "name": label(k), "posts": 0, "views": 0, "expected_rp": 0, "paid_rp": 0})
            g["posts"] += 1
            g["views"] += int(r.get("views") or 0)
            if r["_state"] == "paid":
                g["paid_rp"] += r["_idr"]
            else:
                g["expected_rp"] += r["_idr"]
        res = sorted(out.values(), key=lambda g: (-g["views"], g["name"].lower()))
        for g in res:
            g.update(views_fmt=fmt_views(g["views"]), expected_fmt=payouts.format_idr(g["expected_rp"]),
                     paid_fmt=payouts.format_idr(g["paid_rp"]))
        return res

    views = sum(int(r.get("views") or 0) for r in rows)
    paid = sum(r["_idr"] for r in rows if r["_state"] == "paid")
    expected = sum(r["_idr"] for r in rows if r["_state"] != "paid")
    top = sorted(rows, key=lambda r: -int(r.get("views") or 0))[:TOP_N]
    return {
        "tiles": {
            "posts": len(rows), "views": views, "views_fmt": fmt_views(views),
            "paid_rp": paid, "paid_fmt": payouts.format_idr(paid),
            "expected_rp": expected, "expected_fmt": payouts.format_idr(expected),
            "claimed": sum(1 for r in rows if r["status"] in ("claimed", "paid")),
            "paid": sum(1 for r in rows if r["status"] == "paid"),
            "at_cap": sum(1 for r in rows if r["_cap"]),
        },
        "campaigns": group(lambda r: r.get("campaign"), lambda k: names.get(k, k) if k else "No campaign"),
        "platforms": group(lambda r: r.get("platform"), _platform_name),
        "top": [{
            "post_id": r.get("id"), "candidate_id": r.get("candidate_id"), "job_id": r.get("job_id"),
            "title": r.get("title") or "Untitled clip", "platform": r.get("platform"),
            "platform_name": _platform_name(r.get("platform") or ""),
            "campaign_name": names.get(r.get("campaign"), r.get("campaign")) if r.get("campaign") else None,
            "status": r["status"], "views_fmt": fmt_views(r.get("views")), "url": r.get("url"),
            "amount_fmt": payouts.format_with_idr(r["_amount"], r["_cur"], **rate) if r["_amount"] is not None else "—",
            "amount_state": r["_state"], "at_cap": r["_cap"],
        } for r in top],
        "skipped_currencies": skipped,
    }


# --------------------------------------------------------------------------- views per day (UI phase 2, owner 2026-10-14)
# Track's 30-day line chart. Input = the caller's own clip_post_views snapshots [(post_id, at (aware datetime), views)].
# Per post: the highest count recorded by the end of each WIB day, carried forward; the day's new views = that minus
# the previous day's (never negative: a lower manual correction doesn't count as "lost" views). Summed per day.

from datetime import date as _date, datetime as _datetime, timedelta as _timedelta, timezone as _timezone

WIB = _timezone(_timedelta(hours=7))
DAILY_DAYS = 30


def daily_views(history, today: Optional[_date] = None, days: int = DAILY_DAYS, posted: Optional[dict] = None) -> dict:
    """{days: [{date, views, views_fmt}] oldest first, total, total_fmt, max} for the last `days` WIB days.
    posted = {post_id: posted_at}: a post's first count (no snapshot before the window) goes to the day it was posted
    when that's inside the window, and counts as its baseline when it was posted before (QA c43afce Low: the whole
    lifetime used to land on the first check's day as one spike)."""
    today = today or _datetime.now(WIB).date()
    first = today - _timedelta(days=days - 1)
    by_post: dict = {}
    for post_id, at, views in history or []:
        if at is None or views is None:
            continue
        day = at.astimezone(WIB).date()
        d = by_post.setdefault(post_id, {})
        d[day] = max(d.get(day, 0), int(views))
    totals = [0] * days
    for post_id, snaps in by_post.items():
        best, prev = 0, None
        for day in sorted(k for k in snaps if k < first):       # the baseline before the window
            best = max(best, snaps[day])
        prev = best if any(k < first for k in snaps) else None
        pat = (posted or {}).get(post_id)
        pday = pat.astimezone(WIB).date() if hasattr(pat, "astimezone") else pat
        if prev is None and pday is not None and pday < first:
            best = prev = snaps[min(snaps)]   # posted before the window, first checked inside it: that count is history
        for i in range(days):
            day = first + _timedelta(days=i)
            if day in snaps:
                best = max(best, snaps[day])
            if prev is not None:
                totals[i] += max(0, best - prev)
            elif day in snaps:
                j = (pday - first).days if pday is not None and first <= pday <= day else i
                totals[j] += best                                   # the first count = views since it was posted
            prev = best if (prev is not None or day in snaps) else None
    out = [{"date": (first + _timedelta(days=i)).isoformat(), "views": v, "views_fmt": fmt_views(v)} for i, v in enumerate(totals)]
    total = sum(totals)
    return {"days": out, "total": total, "total_fmt": fmt_views(total), "max": max(totals) if totals else 0}
