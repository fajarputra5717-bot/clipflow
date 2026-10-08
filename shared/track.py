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
