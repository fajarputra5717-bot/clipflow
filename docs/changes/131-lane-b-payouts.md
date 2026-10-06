# 131 · Lane B payout models + claim advice merged to main (shared/payouts.py, tests/test_payouts.py) · from lane-b 92b8bd1

New `shared/payouts.py` (pure, IDR ints, timezone-aware datetimes, pass `now`):
- `FixedThreshold` (IME): Rp 200.000 at 40.000 views on ONE post; WIB week windows (W1–W4,
  inclusive days, close 00:00 WIB next day); claim only inside the upload week; max 2 eligible per
  platform account per WIB calendar month; first come, first served → claim as soon as eligible.
- `PerBlock` (Fandra): Rp 12.000 per FULL 3.000 views, min 3.000, counted up to 500.000 →
  max Rp 1.992.000; one claim per post at submitted views.
- `Unknown`: no estimate.
- `claim_advice(model, views=, uploaded_at=, now=, claimed=, account_claims_this_month=,
  views_24h_ago=, campaign_end=, budget_exhausted=)` → `Advice(action, reason, payout_now, message,
  views_needed, deadline)`; actions `claim_now | wait | missed | claimed | unknown`.
  PerBlock waits while growing ≥ 1 block/24 h; claims when stalled, at the 500k cap, within 24 h
  of campaign end, or 7+ days old without growth data.
- `model_from_rules(rules)` reads docs/campaigns rules (IME → FixedThreshold, Fandra → PerBlock from
  `stated_as`, MotionKlip → Unknown). `format_idr()` → "Rp 1.992.000".

Data issue for Lane A: `fandra-octo.rules.json` `payout.max_payout_per_video = 2000000` is per-view
math (500k × Rp 4); full 3k blocks pay at most Rp 1.992.000. The model ignores that field.
Tests: `tests/test_payouts.py` (16).

## Multi-currency (2026-10-02)

Every model carries `currency` and computes in it: IDR = whole rupiah (int); any other currency =
`Decimal`, never rounded to an integer (cents kept, rounded DOWN so estimates never overstate).
New prorated `Cpm(rate_per_1000, currency, min_views, max_counted_views, max_payout)` for
English/Whop-style briefs ($1.50 CPM: 123,456 views → $185.18). Conversion for totals:
`to_idr(amount, currency, usd_idr=, rates=)`, `total_idr([...])` (returns skipped currencies),
display `format_with_idr()` → "$12.40 (~Rp 204.600)". `claim_advice(..., usd_idr=, rates=)` adds
`currency` + `payout_now_idr` and shows both amounts in messages. `DEFAULT_USD_IDR = 16500` is only a
fallback: **Lane A: add a `USD_IDR_RATE` setting to DEFAULT_SETTINGS and pass its value as
`usd_idr`.** `model_from_rules` reads `payout.currency` (default IDR), `model: cpm`, and
`min_views_to_qualify`; an unstated currency → Unknown. Tests: 6 new.

## Merge note (Lane A, 2026-10-06)

Taken file-wise from origin/lane-b (`shared/payouts.py`, `tests/test_payouts.py`), not a branch merge. 21 Lane B
tests pass on main. Lane A appended a "posting eligibility" section (`campaign_period`, `window_problems`,
`account_cap`, `cap_problem`) + 4 tests (see 132); Lane B: keep it when you next touch the file.
Still open from Lane B's note: `fandra-octo.rules.json` `max_payout_per_video = 2000000` (the model ignores it).
