"""Campaign payout models + claim advice. Pure: no DB, no clock reads (pass `now`).

Money: every model carries its campaign's currency and computes in it. IDR amounts are whole
rupiah (int); every other currency is a Decimal and is NEVER rounded to an integer (cents kept,
rounded down so an estimate never overstates). Totals convert to IDR with an editable rate
(`usd_idr`, default DEFAULT_USD_IDR until Lane A's setting exists; `rates` for other currencies),
and display shows both: "$12.40 (~Rp 204.600)".

Models (from the pilot campaigns, docs/campaigns/*.rules.json):

  FixedThreshold  IME Roleplay: Rp 200.000 once a SINGLE post reaches 40.000 views. The post only
                  counts in the WIB week window it was uploaded in and must be claimed inside that
                  same window; max 2 eligible posts per platform account per calendar month; the
                  weekly budget is first come, first served (so: claim as soon as eligible).
  PerBlock        Fandra Octo: Rp 12.000 per FULL 3.000 views, min 3.000, views counted up to
                  500.000 → max floor(500000/3000) × 12.000 = Rp 1.992.000. One claim per post, paid
                  on the views at submit time (so waiting pays more until the cap, but the budget
                  can run out).
  Cpm             English/Whop style: amount per 1,000 views, prorated (e.g. $1.50 CPM), optional
                  min views to qualify, counted-views cap and per-post payout cap.
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
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Iterable, Optional, Union

WIB = timezone(timedelta(hours=7), "WIB")
DEFAULT_USD_IDR = Decimal("16500")   # until the USD→IDR setting is set; always pass the setting's value
Money = Union[int, Decimal]
_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "SGD": "S$", "AUD": "A$"}
_CENT = Decimal("0.01")

# PerBlock advice tuning (caller may override per call)
STALL_GAIN_BLOCKS = 1.0     # < 1 more block gained in the last 24 h → growth has stalled: claim
SETTLED_AGE_DAYS = 7        # no velocity data and the post is this old → views have settled: claim
ENDING_SOON_HOURS = 24      # campaign ends within this → claim


def format_idr(amount: Optional[int]) -> str:
    """1992000 → 'Rp 1.992.000' (Indonesian thousands separator); None → 'Rp ?'."""
    if amount is None:
        return "Rp ?"
    return "Rp " + f"{int(amount):,}".replace(",", ".")


def as_money(x, currency: str = "IDR") -> Money:
    """Parse an amount for its currency: IDR → int rupiah, anything else → exact Decimal."""
    d = x if isinstance(x, Decimal) else Decimal(str(x))
    return int(d.to_integral_value(ROUND_DOWN)) if currency == "IDR" else d


def format_money(amount: Optional[Money], currency: str = "IDR") -> str:
    """'Rp 1.992.000' / '$12.40' / '€3.05' / '12.40 CHF'; None → '?' in that currency."""
    if currency == "IDR":
        return format_idr(None if amount is None else int(amount))
    sym = _SYMBOLS.get(currency)
    if amount is None:
        return f"{sym}?" if sym else f"? {currency}"
    txt = f"{Decimal(amount).quantize(_CENT, ROUND_DOWN):,.2f}"
    return f"{sym}{txt}" if sym else f"{txt} {currency}"


def to_idr(amount: Optional[Money], currency: str = "IDR", *, usd_idr: Decimal = DEFAULT_USD_IDR,
           rates: Optional[dict] = None) -> Optional[int]:
    """Amount in whole rupiah for totals; None when the currency has no rate."""
    if amount is None:
        return None
    if currency == "IDR":
        return int(amount)
    rate = Decimal(str(usd_idr)) if currency == "USD" else (rates or {}).get(currency)
    if rate is None:
        return None
    return int((Decimal(amount) * Decimal(str(rate))).quantize(Decimal(1), ROUND_HALF_UP))


def format_with_idr(amount: Optional[Money], currency: str = "IDR", **rate) -> str:
    """'$12.40 (~Rp 204.600)'; IDR amounts show once ('Rp 200.000')."""
    if currency == "IDR":
        return format_money(amount, "IDR")
    return f"{format_money(amount, currency)} (~{format_idr(to_idr(amount, currency, **rate))})"


def total_idr(items: Iterable[tuple[Optional[Money], str]], **rate) -> tuple[int, list[str]]:
    """Sum (amount, currency) pairs in IDR → (total, currencies that had no rate and were skipped)."""
    total, skipped = 0, []
    for amount, cur in items:
        v = to_idr(amount, cur, **rate)
        if v is None:
            if amount is not None and cur not in skipped:
                skipped.append(cur)
            continue
        total += v
    return total, skipped


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
    currency: str = "IDR"
    kind: str = field(default="fixed_threshold", init=False)


@dataclass(frozen=True)
class PerBlock:
    per_block: int
    block_views: int
    min_views: int
    max_counted_views: Optional[int] = None
    claims_per_post: int = 1
    currency: str = "IDR"
    kind: str = field(default="per_block", init=False)


@dataclass(frozen=True)
class Cpm:
    """Prorated: views × rate / 1000 (cents kept, rounded down), capped by views and/or payout."""
    rate_per_1000: Money
    currency: str = "IDR"
    min_views: int = 0
    max_counted_views: Optional[int] = None
    max_payout: Optional[Money] = None
    claims_per_post: int = 1
    kind: str = field(default="cpm", init=False)


@dataclass(frozen=True)
class Unknown:
    note: str = ""
    currency: str = "IDR"
    kind: str = field(default="unknown", init=False)


Model = Union[FixedThreshold, PerBlock, Cpm, Unknown]


def payout_for(model: Model, views: int) -> Optional[Money]:
    """What the post would pay if claimed at `views` (ignores windows/slots/budget), in the
    campaign's currency (IDR int, else Decimal). None = unknown."""
    views = max(0, int(views))
    if isinstance(model, Cpm):
        if views < model.min_views:
            return as_money(0, model.currency)
        counted = min(views, model.max_counted_views) if model.max_counted_views else views
        amount = Decimal(counted) * Decimal(model.rate_per_1000) / 1000
        amount = amount.quantize(Decimal(1) if model.currency == "IDR" else _CENT, ROUND_DOWN)
        if model.max_payout is not None:
            amount = min(amount, Decimal(model.max_payout))
        return as_money(amount, model.currency)
    if isinstance(model, FixedThreshold):
        return model.amount if views >= model.min_views else 0
    if isinstance(model, PerBlock):
        if views < model.min_views:
            return 0
        counted = min(views, model.max_counted_views) if model.max_counted_views else views
        return (counted // model.block_views) * model.per_block
    return None


def max_payout(model: Model) -> Optional[Money]:
    """Most one post can earn; None = unbounded or unknown."""
    if isinstance(model, FixedThreshold):
        return model.amount
    if isinstance(model, Cpm):
        if model.max_payout is not None:
            return model.max_payout
        return payout_for(model, model.max_counted_views) if model.max_counted_views else None
    if isinstance(model, PerBlock) and model.max_counted_views:
        return payout_for(model, model.max_counted_views)
    return None


def window_for(model: FixedThreshold, uploaded_at: datetime) -> Optional[Window]:
    return next((w for w in model.windows if w.contains(uploaded_at)), None)


def month_key(dt: datetime) -> str:
    """Calendar month in WIB ('2026-10'): the unit of the per-account monthly limit."""
    return _wib(dt).strftime("%Y-%m")


def _unit_views(m) -> int:
    """Views worth 'one more step' when judging growth: a block, or 1,000 for CPM."""
    return m.block_views if isinstance(m, PerBlock) else 1000


def _next_needed(m, views: int) -> Optional[int]:
    """Views until the next paid increment; None when nothing more can be earned (cap)."""
    if isinstance(m, PerBlock):
        return views_to_next_block(m, views)
    if views < m.min_views:
        return m.min_views - views
    capped_views = m.max_counted_views and views >= m.max_counted_views
    capped_pay = m.max_payout is not None and payout_for(m, views) >= Decimal(m.max_payout)
    return None if capped_views or capped_pay else 1


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
    payout_now: Optional[Money]     # campaign currency if claimed now (0 = nothing yet), None = unknown
    message: str
    views_needed: Optional[int] = None
    deadline: Optional[datetime] = None
    currency: str = "IDR"
    payout_now_idr: Optional[int] = None   # payout_now converted for totals (None = no rate)


def claim_advice(model: Model, *, views: int, uploaded_at: datetime, now: datetime,
                 claimed: bool = False, account_claims_this_month: int = 0,
                 views_24h_ago: Optional[int] = None, campaign_end: Optional[datetime] = None,
                 budget_exhausted: bool = False, usd_idr: Decimal = DEFAULT_USD_IDR,
                 rates: Optional[dict] = None) -> Advice:
    """Claim advice for ONE post on ONE platform account.

    account_claims_this_month  eligible posts already claimed on this platform account in the
                               WIB calendar month of this upload (FixedThreshold limit).
    views_24h_ago              views a day ago, for PerBlock growth (None = unknown).
    budget_exhausted           budget for this post's window/campaign is gone (FCFS).
    usd_idr / rates            conversion for payout_now_idr and the "(~Rp …)" in messages.
    """
    a = _advice(model, views=views, uploaded_at=uploaded_at, now=now, claimed=claimed,
                used=account_claims_this_month, views_24h_ago=views_24h_ago, campaign_end=campaign_end,
                budget_exhausted=budget_exhausted,
                fmt=lambda amt: format_with_idr(amt, model.currency, usd_idr=usd_idr, rates=rates))
    cur = model.currency
    return Advice(**{**a.__dict__, "currency": cur,
                     "payout_now_idr": to_idr(a.payout_now, cur, usd_idr=usd_idr, rates=rates)})


def _advice(model, *, views, uploaded_at, now, claimed, used, views_24h_ago, campaign_end,
            budget_exhausted, fmt) -> Advice:
    _wib(now), _wib(uploaded_at)
    pay = payout_for(model, views)
    if claimed:
        return Advice("claimed", "already_claimed", pay, "Already claimed.")
    if isinstance(model, Unknown):
        return Advice("unknown", "unknown_model", None,
                      "Payout model unknown: check the brief before claiming." + (f" {model.note}" if model.note else ""))
    if isinstance(model, FixedThreshold):
        return _fixed_advice(model, views, uploaded_at, now, used, budget_exhausted, pay, fmt)
    return _block_advice(model, views, uploaded_at, now, views_24h_ago, campaign_end, budget_exhausted, pay, fmt)


def _fixed_advice(m: FixedThreshold, views, uploaded_at, now, used, budget_exhausted, pay, fmt) -> Advice:
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
                      f"{views:,} views ≥ {m.min_views:,}: claim {fmt(pay)} now; "
                      + ("the weekly budget is first come, first served." if m.first_come_first_served
                         else "more views pay nothing extra."), deadline=deadline)
    need = m.min_views - views
    left = f", {_hours(deadline - now)} left in week {win.id}" if deadline else ""
    return Advice("wait", "below_target", 0, f"Needs {need:,} more views{left}.",
                  views_needed=need, deadline=deadline)


def _block_advice(m: Union[PerBlock, Cpm], views, uploaded_at, now, views_24h_ago, campaign_end,
                  budget_exhausted, pay, fmt) -> Advice:
    if campaign_end and now >= campaign_end:
        return Advice("missed", "campaign_ended", 0, "The campaign has ended.")
    if budget_exhausted:
        return Advice("missed", "budget_exhausted", 0, "The campaign budget is used up.")
    if views < m.min_views:
        need = m.min_views - views
        return Advice("wait", "below_minimum", 0, f"Needs {need:,} more views to reach the minimum.",
                      views_needed=need)
    nxt = _next_needed(m, views)
    if nxt is None:
        return Advice("claim_now", "at_cap", pay, f"At the cap: claim {fmt(pay)} now; more views pay nothing.")
    if campaign_end and campaign_end - now <= timedelta(hours=ENDING_SOON_HOURS):
        return Advice("claim_now", "ending_soon", pay,
                      f"Campaign ends in {_hours(campaign_end - now)}: claim {fmt(pay)} now.",
                      deadline=campaign_end)
    if views_24h_ago is not None:
        gain = max(0, views - views_24h_ago)
        if gain < STALL_GAIN_BLOCKS * _unit_views(m):
            return Advice("claim_now", "growth_stalled", pay,
                          f"Only +{gain:,} views in 24 h: claim {fmt(pay)} now (one claim per post).")
        nxt_pay = payout_for(m, views + gain)
        return Advice("wait", "still_growing", pay,
                      f"+{gain:,} views in 24 h; {fmt(pay)} now, about {fmt(nxt_pay)} "
                      "tomorrow at this pace. One claim per post, so wait while it grows.",
                      views_needed=nxt)
    if now - _wib(uploaded_at) >= timedelta(days=SETTLED_AGE_DAYS):
        return Advice("claim_now", "settled", pay,
                      f"Posted {SETTLED_AGE_DAYS}+ days ago, views have mostly settled: "
                      f"claim {fmt(pay)} now.")
    return Advice("wait", "early", pay,
                  f"{fmt(pay)} so far; young post and no growth data yet. One claim per post.",
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
    cur = (p.get("currency") or "IDR").upper()
    if cur in ("UNSTATED", "?", ""):
        return Unknown("payout currency not stated in the brief")
    mq = (rules or {}).get("min_views_to_qualify")
    if p.get("model") == "cpm":
        rate = p.get("rate_per_1000") or p.get("rate")
        if not rate:
            return Unknown("cpm without a rate")
        return Cpm(rate_per_1000=as_money(rate, cur), currency=cur, min_views=int(p.get("min_views") or mq or 0),
                   max_counted_views=p.get("max_paid_views_per_video"),
                   max_payout=as_money(p["max_payout_per_video"], cur) if p.get("max_payout_per_video") else None,
                   claims_per_post=int(p.get("claims_per_video") or 1))
    if p.get("model") == "fixed_threshold" or (p.get("per_video") and p.get("min_views")):
        weeks = ((rules or {}).get("weeks") or {}).get("list") or []
        lim = (rules or {}).get("limits") or {}
        return FixedThreshold(
            amount=as_money(p.get("amount") or p["per_video"], cur), min_views=int(p["min_views"]), currency=cur,
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
        return PerBlock(per_block=as_money(per_block, cur), block_views=int(block), currency=cur,
                        min_views=int(p.get("min_views") or mq or block),
                        max_counted_views=p.get("max_paid_views_per_video") or p.get("max_counted_views"),
                        claims_per_post=int(p.get("claims_per_video") or 1))
    return Unknown(f"unrecognised payout: {p.get('model') or p.get('stated_as') or 'no model'}")


# --------------------------------------------------------------------------- posting eligibility
# Lane A, P2 part 4 (131): pre-post checks for the Publish step. They WARN; a post made anyway is
# recorded as not eligible with these reasons (clip_posts.eligible / ineligible_reason).

def campaign_period(rules: Optional[dict]) -> tuple[Optional[date], Optional[date]]:
    """rules["period"] start/end (ISO dates, inclusive, WIB); None = open."""
    per = (rules or {}).get("period") or {}

    def d(v):
        try:
            return date.fromisoformat(str(v)) if v else None
        except ValueError:
            return None
    return d(per.get("start")), d(per.get("end"))


def _day(d: date) -> str:
    return f"{d.day} {d.strftime('%b')}"


def window_problems(rules: Optional[dict], model: Model, when: datetime, campaign_name: str = "") -> list[dict]:
    """Is a post made at `when` inside the campaign's posting window? [] = yes.
    Period (any model) + week windows (FixedThreshold: IME W1–W4; days outside every
    week, e.g. 29–31 Oct, are not eligible)."""
    out, day, name = [], _wib(when).date(), campaign_name or "the campaign"
    start, end = campaign_period(rules)
    if start and day < start:
        out.append({"code": "before_start", "message": f"Before {name} starts ({_day(start)})"})
    if end and day > end:
        out.append({"code": "after_end", "message": f"After {name} ended ({_day(end)})"})
    if isinstance(model, FixedThreshold) and model.windows and not any(w.contains(when) for w in model.windows):
        first, last = model.windows[0], model.windows[-1]
        out.append({"code": "outside_window",
                    "message": f"Outside {name} week window ({first.id}–{last.id}: {_day(first.start)}–{_day(last.end)})"})
    return out


def account_cap(model: Model) -> Optional[int]:
    """Eligible posts allowed per platform account per WIB calendar month (None = no cap)."""
    return getattr(model, "max_eligible_per_account_month", None)


def cap_problem(model: Model, used_this_month: int, handle: str, platform_name: str) -> Optional[dict]:
    cap = account_cap(model)
    if cap is not None and used_this_month >= cap:
        return {"code": "account_cap",
                "message": f"Cap reached for @{handle} on {platform_name} this month ({used_this_month} of {cap})"}
    return None
