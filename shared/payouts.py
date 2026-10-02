"""Campaign payout models + claim advice. Pure: no DB, no clock reads (pass `now`), IDR integers.

Models (from the pilot campaigns, docs/campaigns/*.rules.json):

  FixedThreshold  IME Roleplay: Rp 200.000 once a SINGLE post reaches 40.000 views. The post only
                  counts in the WIB week window it was uploaded in and must be claimed inside that
                  same window; max 2 eligible posts per platform account per calendar month; the
                  weekly budget is first come, first served (so: claim as soon as eligible).
  PerBlock        Fandra Octo: Rp 12.000 per FULL 3.000 views, min 3.000, views counted up to
                  500.000 → max floor(500000/3000) × 12.000 = Rp 1.992.000. One claim per post, paid
                  on the views at submit time (so waiting pays more until the cap, but the budget
                  can run out).
  Unknown         anything else: no estimate, advice says check manually.

`claim_advice()` turns a post's state into one action:
  claim_now   eligible now and waiting gains nothing (or risks losing it)
  wait        not eligible yet, or still earning more by waiting
  missed      can no longer be paid (window closed, slots used, budget gone, campaign over)
  claimed     already claimed (nothing to do)
  unknown     payout model unknown
plus a machine `reason`, the payout if claimed now, and a short English message.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional, Union

WIB = timezone(timedelta(hours=7), "WIB")

# PerBlock advice tuning (caller may override per call)
STALL_GAIN_BLOCKS = 1.0     # < 1 more block gained in the last 24 h → growth has stalled: claim
SETTLED_AGE_DAYS = 7        # no velocity data and the post is this old → views have settled: claim
ENDING_SOON_HOURS = 24      # campaign ends within this → claim


def format_idr(amount: Optional[int]) -> str:
    """1992000 → 'Rp 1.992.000' (Indonesian thousands separator); None → 'Rp ?'."""
    if amount is None:
        return "Rp ?"
    return "Rp " + f"{int(amount):,}".replace(",", ".")


def _wib(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("timezone-aware datetime required")
    return dt.astimezone(WIB)


# --------------------------------------------------------------------------- models

@dataclass(frozen=True)
class Window:
    """Inclusive WIB calendar days [start, end]."""
    id: str
    start: date
    end: date

    def contains(self, dt: datetime) -> bool:
        return self.start <= _wib(dt).date() <= self.end

    def closes_at(self) -> datetime:
        """First instant after the window (00:00 WIB the next day)."""
        return datetime.combine(self.end + timedelta(days=1), time(0), WIB)


@dataclass(frozen=True)
class FixedThreshold:
    amount: int
    min_views: int
    windows: tuple[Window, ...] = ()
    max_eligible_per_account_month: Optional[int] = None
    claim_in_upload_window: bool = True
    first_come_first_served: bool = True
    kind: str = field(default="fixed_threshold", init=False)


@dataclass(frozen=True)
class PerBlock:
    per_block: int
    block_views: int
    min_views: int
    max_counted_views: Optional[int] = None
    claims_per_post: int = 1
    kind: str = field(default="per_block", init=False)


@dataclass(frozen=True)
class Unknown:
    note: str = ""
    kind: str = field(default="unknown", init=False)


Model = Union[FixedThreshold, PerBlock, Unknown]


def payout_for(model: Model, views: int) -> Optional[int]:
    """What the post would pay if claimed at `views` (ignores windows/slots/budget). None = unknown."""
    views = max(0, int(views))
    if isinstance(model, FixedThreshold):
        return model.amount if views >= model.min_views else 0
    if isinstance(model, PerBlock):
        if views < model.min_views:
            return 0
        counted = min(views, model.max_counted_views) if model.max_counted_views else views
        return (counted // model.block_views) * model.per_block
    return None


def max_payout(model: Model) -> Optional[int]:
    """Most one post can earn; None = unbounded or unknown."""
    if isinstance(model, FixedThreshold):
        return model.amount
    if isinstance(model, PerBlock) and model.max_counted_views:
        return payout_for(model, model.max_counted_views)
    return None


def window_for(model: FixedThreshold, uploaded_at: datetime) -> Optional[Window]:
    return next((w for w in model.windows if w.contains(uploaded_at)), None)


def month_key(dt: datetime) -> str:
    """Calendar month in WIB ('2026-10'): the unit of the per-account monthly limit."""
    return _wib(dt).strftime("%Y-%m")


def views_to_next_block(model: PerBlock, views: int) -> Optional[int]:
    """Views still needed for the next paid block; None when at the counted cap."""
    target = max(model.min_views, (views // model.block_views + 1) * model.block_views)
    if model.max_counted_views and target > model.max_counted_views:
        return None
    return target - views


# --------------------------------------------------------------------------- advice

@dataclass(frozen=True)
class Advice:
    action: str                     # claim_now | wait | missed | claimed | unknown
    reason: str                     # machine code, see claim_advice()
    payout_now: Optional[int]       # IDR if claimed now (0 = nothing yet), None = unknown
    message: str
    views_needed: Optional[int] = None
    deadline: Optional[datetime] = None


def claim_advice(model: Model, *, views: int, uploaded_at: datetime, now: datetime,
                 claimed: bool = False, account_claims_this_month: int = 0,
                 views_24h_ago: Optional[int] = None, campaign_end: Optional[datetime] = None,
                 budget_exhausted: bool = False) -> Advice:
    """Claim advice for ONE post on ONE platform account.

    account_claims_this_month  eligible posts already claimed on this platform account in the
                               WIB calendar month of this upload (FixedThreshold limit).
    views_24h_ago              views a day ago, for PerBlock growth (None = unknown).
    budget_exhausted           budget for this post's window/campaign is gone (FCFS).
    """
    _wib(now), _wib(uploaded_at)
    pay = payout_for(model, views)
    if claimed:
        return Advice("claimed", "already_claimed", pay, "Already claimed.")
    if isinstance(model, Unknown):
        return Advice("unknown", "unknown_model", None,
                      "Payout model unknown: check the brief before claiming." + (f" {model.note}" if model.note else ""))
    if isinstance(model, FixedThreshold):
        return _fixed_advice(model, views, uploaded_at, now, account_claims_this_month, budget_exhausted, pay)
    return _block_advice(model, views, uploaded_at, now, views_24h_ago, campaign_end, budget_exhausted, pay)


def _fixed_advice(m: FixedThreshold, views, uploaded_at, now, used, budget_exhausted, pay) -> Advice:
    win = window_for(m, uploaded_at) if m.windows else None
    if m.windows and win is None:
        return Advice("missed", "outside_windows", 0,
                      "Uploaded outside the campaign weeks: not eligible.")
    if m.max_eligible_per_account_month is not None and used >= m.max_eligible_per_account_month:
        return Advice("missed", "account_limit_reached", 0,
                      f"This account already has {used} eligible posts this month "
                      f"(max {m.max_eligible_per_account_month}).")
    deadline = win.closes_at() if (win and m.claim_in_upload_window) else None
    if deadline and now >= deadline:
        if views >= m.min_views:
            return Advice("missed", "window_closed", 0,
                          f"Reached {views:,} views but week {win.id} closed without a claim.", deadline=deadline)
        return Advice("missed", "window_closed_below_target", 0,
                      f"Week {win.id} closed at {views:,}/{m.min_views:,} views.", deadline=deadline)
    if budget_exhausted:
        return Advice("missed", "budget_exhausted", 0,
                      "This week's budget is used up (first come, first served).", deadline=deadline)
    if views >= m.min_views:
        return Advice("claim_now", "threshold_reached", pay,
                      f"{views:,} views ≥ {m.min_views:,}: claim {format_idr(pay)} now; "
                      + ("the weekly budget is first come, first served." if m.first_come_first_served
                         else "more views pay nothing extra."), deadline=deadline)
    need = m.min_views - views
    left = f", {_hours(deadline - now)} left in week {win.id}" if deadline else ""
    return Advice("wait", "below_target", 0, f"Needs {need:,} more views{left}.",
                  views_needed=need, deadline=deadline)


def _block_advice(m: PerBlock, views, uploaded_at, now, views_24h_ago, campaign_end,
                  budget_exhausted, pay) -> Advice:
    if campaign_end and now >= campaign_end:
        return Advice("missed", "campaign_ended", 0, "The campaign has ended.")
    if budget_exhausted:
        return Advice("missed", "budget_exhausted", 0, "The campaign budget is used up.")
    if views < m.min_views:
        need = m.min_views - views
        return Advice("wait", "below_minimum", 0, f"Needs {need:,} more views to reach the minimum.",
                      views_needed=need)
    nxt = views_to_next_block(m, views)
    if nxt is None:
        return Advice("claim_now", "at_cap", pay,
                      f"At the {m.max_counted_views:,}-view cap: claim {format_idr(pay)} now; "
                      "more views pay nothing.")
    if campaign_end and campaign_end - now <= timedelta(hours=ENDING_SOON_HOURS):
        return Advice("claim_now", "ending_soon", pay,
                      f"Campaign ends in {_hours(campaign_end - now)}: claim {format_idr(pay)} now.",
                      deadline=campaign_end)
    if views_24h_ago is not None:
        gain = max(0, views - views_24h_ago)
        if gain < STALL_GAIN_BLOCKS * m.block_views:
            return Advice("claim_now", "growth_stalled", pay,
                          f"Only +{gain:,} views in 24 h: claim {format_idr(pay)} now (one claim per post).")
        nxt_pay = payout_for(m, views + gain)
        return Advice("wait", "still_growing", pay,
                      f"+{gain:,} views in 24 h; {format_idr(pay)} now, about {format_idr(nxt_pay)} "
                      "tomorrow at this pace. One claim per post, so wait while it grows.",
                      views_needed=nxt)
    if now - _wib(uploaded_at) >= timedelta(days=SETTLED_AGE_DAYS):
        return Advice("claim_now", "settled", pay,
                      f"Posted {SETTLED_AGE_DAYS}+ days ago, views have mostly settled: "
                      f"claim {format_idr(pay)} now.")
    return Advice("wait", "early", pay,
                  f"{format_idr(pay)} so far; young post and no growth data yet. One claim per post.",
                  views_needed=nxt)


def _hours(td: timedelta) -> str:
    h = max(0, int(td.total_seconds() // 3600))
    return f"{h // 24} d {h % 24} h" if h >= 24 else f"{h} h"


# --------------------------------------------------------------------------- from rules

_STATED = re.compile(r"Rp\s*([\d.]+)\s*(?:per|/)\s*([\d.]+)\s*views", re.I)


def _int(s) -> int:
    return int(str(s).replace(".", "").replace(",", ""))


def model_from_rules(rules: Optional[dict]) -> Model:
    """Model from a docs/campaigns rules dict (or brief_parser output). Unknown when unsure."""
    p = (rules or {}).get("payout") or {}
    if not p:
        return Unknown("no payout section")
    if p.get("model") == "fixed_threshold" or (p.get("per_video") and p.get("min_views")):
        weeks = ((rules or {}).get("weeks") or {}).get("list") or []
        lim = (rules or {}).get("limits") or {}
        return FixedThreshold(
            amount=int(p.get("amount") or p["per_video"]), min_views=int(p["min_views"]),
            windows=tuple(Window(w["id"], date.fromisoformat(w["start"]), date.fromisoformat(w["end"]))
                          for w in weeks),
            max_eligible_per_account_month=lim.get("max_eligible_videos_per_platform_account_per_month"),
        )
    per_block, block = p.get("per_block"), p.get("block_views")
    if not (per_block and block):
        m = _STATED.search(p.get("stated_as") or "")
        if m:
            per_block, block = _int(m.group(1)), _int(m.group(2))
    if per_block and block:
        return PerBlock(per_block=int(per_block), block_views=int(block),
                        min_views=int(p.get("min_views") or block),
                        max_counted_views=p.get("max_paid_views_per_video") or p.get("max_counted_views"),
                        claims_per_post=int(p.get("claims_per_video") or 1))
    return Unknown(f"unrecognised payout: {p.get('model') or p.get('stated_as') or 'no model'}")
