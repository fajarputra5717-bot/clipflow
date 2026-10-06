"""Daily 09:00 WIB digest for ONE user (P2 part 6b, 142): read-only queries, text for Telegram.

Sections (each only when non-empty; nothing at all → None, no message):
  • Ready to post — finished clips × allowed platform without a live post (same rows as the Publish step).
  • Claim now — posted posts whose payouts.claim_advice says claim_now (payout + deadline).
  • Deadlines — waiting posts whose claim window closes within 48 h (views still needed).
  • Update views — posted posts whose views are older than 24 h (advice needs fresh numbers).
  • Campaign weeks — for week-window campaigns (IME) the user has clips in: the open week and when it closes.
Money comes formatted from shared/payouts.py; scoping: every query filters by user_id."""

from datetime import datetime, timedelta

from shared import campaigns, payouts, post_advice, posts as post_rules, rule_checks

MAX_LINES = 5


def _fmt_when(dt: datetime) -> str:
    w = dt.astimezone(payouts.WIB)
    return f"{w:%a %d %b %H:%M} WIB"


def _ready(cur, user_id):
    cur.execute(
        """
        SELECT c.id, j.campaign, j.platform, COALESCE(NULLIF(c.manual_title, ''), NULLIF(c.title, ''), c.ai_title)
        FROM clip_candidates c JOIN jobs j ON j.id = c.job_id
        WHERE j.user_id = %s AND c.status = 'completed' AND COALESCE(c.final_path, '') <> ''
          AND j.status IS DISTINCT FROM 'cancelled'
        ORDER BY c.rendered_at DESC NULLS LAST LIMIT 300
        """,
        (user_id,),
    )
    clips = cur.fetchall()
    cur.execute(
        "SELECT candidate_id, platform FROM clip_posts WHERE user_id = %s AND status <> 'dropped'",
        (user_id,),
    )
    live = set(cur.fetchall())
    out = []
    for cid, camp, job_platform, title in clips:
        rules = campaigns.get(camp) if camp else None
        plats = ([p for p in campaigns.platforms(rules) if p in rule_checks.PLATFORM_LIMITS] if rules
                 else [post_rules.JOB_PLATFORM.get(job_platform or "", "youtube")])
        missing = [p for p in plats if (cid, p) not in live]
        if missing:
            out.append((title or "Untitled clip", campaigns.display_name(rules) if rules else None, missing))
    return out


def _posted(cur, user_id):
    cur.execute(
        """
        SELECT id, campaign, status, views, views_at, posted_at, account_id, eligible, ineligible_reason, title, platform
        FROM clip_posts WHERE user_id = %s AND status = 'posted' ORDER BY posted_at DESC LIMIT 200
        """,
        (user_id,),
    )
    keys = ("id", "campaign", "status", "views", "views_at", "posted_at", "account_id", "eligible",
            "ineligible_reason", "title", "platform")
    return [dict(zip(keys, r)) for r in cur.fetchall()]


def build(cur, user_id: str, now: datetime) -> str | None:
    lines = []
    ready = _ready(cur, user_id)
    if ready:
        n = sum(len(m) for _, _, m in ready)
        lines.append(f"📤 Ready to post: {n} ({len(ready)} clip{'s' if len(ready) != 1 else ''})")
        for title, camp, missing in ready[:MAX_LINES]:
            names = ", ".join(rule_checks.PLATFORM_LIMITS[p][2] for p in missing)
            lines.append(f"  • {title[:60]}{f' [{camp}]' if camp else ''}: {names}")
        if len(ready) > MAX_LINES:
            lines.append(f"  … +{len(ready) - MAX_LINES} more in Publish")

    claim, soon, stale = [], [], []
    for p in _posted(cur, user_id):
        if not p["campaign"]:
            continue
        if not p["views_at"] or now - p["views_at"] > timedelta(hours=24):
            stale.append(p)
        a = post_advice.advice_for(cur, user_id, p, now)
        if not a:
            continue
        dl = post_advice.as_ts(a.get("deadline"))
        if a["action"] == "claim_now":
            claim.append((p, a, dl))
        elif a["action"] == "wait" and dl and dl - now <= timedelta(hours=48):
            soon.append((p, a, dl))
    if claim:
        lines.append(f"💰 Claim now: {len(claim)}")
        for p, a, dl in claim[:MAX_LINES]:
            lines.append(f"  • {(p['title'] or 'Clip')[:50]} ({p['platform']}): {a['payout_now_fmt'] or ''}"
                         + (f", by {_fmt_when(dl)}" if dl else ""))
    if soon:
        lines.append(f"⏳ Closing within 48 h: {len(soon)}")
        for p, a, dl in soon[:MAX_LINES]:
            need = f"needs {a['views_needed']:,} more views".replace(",", ".") if a.get("views_needed") else ""
            lines.append(f"  • {(p['title'] or 'Clip')[:50]} ({p['platform']}): {need}, closes {_fmt_when(dl)}")
    if stale:
        lines.append(f"👀 Update views on {len(stale)} posted clip{'s' if len(stale) != 1 else ''} (older than 24 h)")

    cur.execute("SELECT DISTINCT campaign FROM jobs WHERE user_id = %s AND campaign IS NOT NULL", (user_id,))
    for (slug,) in cur.fetchall():
        rules = campaigns.get(slug)
        model = payouts.model_from_rules(rules) if rules else None
        if isinstance(model, payouts.FixedThreshold) and model.windows:
            w = payouts.window_for(model, now)
            name = campaigns.display_name(rules)
            if w:
                lines.append(f"🗓 {name}: week {w.id} open, closes {_fmt_when(w.closes_at() - timedelta(minutes=1))}")
            elif now < datetime.combine(model.windows[0].start, datetime.min.time(), payouts.WIB):
                lines.append(f"🗓 {name}: first week {model.windows[0].id} starts {model.windows[0].start:%d %b}")
    if not lines:
        return None
    return f"☀️ ClipFlow · your day ({now.astimezone(payouts.WIB):%a %d %b})\n" + "\n".join(lines)
