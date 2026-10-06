"""Claim advice for one clip_posts row (P2 133; moved here in 142 so the backend's Publish rows and the
notifier's daily digest use the same code). DB access through a plain psycopg cursor (tuple rows);
payout logic stays in shared/payouts.py."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from shared import campaigns, payouts


def as_ts(value) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        ts = value
    else:
        ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def wib_month_bounds(when: datetime) -> tuple[datetime, datetime]:
    w = when.astimezone(payouts.WIB)
    start = w.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = (start + timedelta(days=32)).replace(day=1)
    return start, end


def views_day_ago(cur, post_id: str, now: datetime) -> Optional[int]:
    """Views from an entry 18–48 h old (the newest such), for claim_advice's 24 h growth; None = no data."""
    cur.execute(
        """
        SELECT views FROM clip_post_views
        WHERE post_id = %s AND at <= %s AND at >= %s ORDER BY at DESC LIMIT 1
        """,
        (post_id, now - timedelta(hours=18), now - timedelta(hours=48)),
    )
    row = cur.fetchone()
    return int(row[0]) if row else None


def claims_this_month(cur, user_id: str, post: dict) -> int:
    """Eligible claimed/paid posts on this account + campaign in the WIB month of this upload (not this one)."""
    posted = as_ts(post.get("posted_at"))
    if not post.get("account_id") or not posted:
        return 0
    start, end = wib_month_bounds(posted)
    cur.execute(
        """
        SELECT COUNT(*) FROM clip_posts
        WHERE user_id = %s AND account_id = %s AND campaign IS NOT DISTINCT FROM %s AND id <> %s
          AND eligible AND status IN ('claimed', 'paid') AND posted_at >= %s AND posted_at < %s
        """,
        (user_id, post["account_id"], post.get("campaign"), post["id"], start, end),
    )
    return cur.fetchone()[0]


def advice_for(cur, user_id: str, post: dict, now: datetime) -> Optional[dict]:
    """payouts.claim_advice for a posted/claimed/paid post; None for planned/dropped or no campaign."""
    if post["status"] not in ("posted", "claimed", "paid") or not post.get("campaign"):
        return None
    rules = campaigns.get(post["campaign"])
    if not rules:
        return None
    if post.get("eligible") is False:
        return {"action": "missed", "reason": "not_eligible", "message": post.get("ineligible_reason") or "Not eligible",
                "payout_now_fmt": None, "payout_now_rp": None, "views_needed": None, "deadline": None}
    model = payouts.model_from_rules(rules)
    _, end = payouts.campaign_period(rules)
    a = payouts.claim_advice(
        model, views=int(post.get("views") or 0), uploaded_at=as_ts(post["posted_at"]), now=now,
        claimed=post["status"] in ("claimed", "paid"),
        account_claims_this_month=claims_this_month(cur, user_id, post),
        views_24h_ago=views_day_ago(cur, post["id"], now),
        campaign_end=datetime.combine(end + timedelta(days=1), datetime.min.time(), payouts.WIB) if end else None,
    )
    return {"action": a.action, "reason": a.reason, "message": a.message,
            "payout_now_fmt": payouts.format_with_idr(a.payout_now, a.currency) if a.payout_now is not None else None,
            "payout_now_rp": payouts.to_idr(a.payout_now, a.currency) if a.payout_now is not None else None,
            "views_needed": a.views_needed, "deadline": a.deadline.isoformat() if a.deadline else None}
