# QA review · df5445a (lane-b) · shared/payouts.py: payout models + claim advice, IDR

Reviewer: Lane C · 2026-10-02 · library only (not on main yet; P2/P3 per roadmap)

Tests: `python -m unittest tests.test_payouts` on df5445a: **16 OK**. QA probes against the real rules files:
- fandra-octo → `PerBlock(12.000 / 3.000 views, min 3.000, cap 500.000)`: 2.999 → Rp 0, 3.000 → Rp 12.000,
  5.999 → Rp 12.000, 6.000 → Rp 24.000, 499.999 / 500.000 / 10.000.000 → **Rp 1.992.000** (= roadmap max) ✓
- ime-roleplay → `FixedThreshold(200.000 at ≥ 40.000, W1–W4, max 2/account/month)`: 39.999 → Rp 0,
  40.000+ → Rp 200.000 ✓ · WIB boundary: upload 2026-10-07 23:30 WIB → W1, 2026-10-08 00:30 WIB → W2 ✓
- motionklip-windah → `Unknown` → "Rp ?" and "check the brief" advice ✓
- `format_idr`: Rp 1.992.000 / Rp 0 / Rp ? ✓

## Findings (most severe first)
1. **Medium · uploads outside the hard-coded weeks are told "not eligible".** `_fixed_advice()`
   (`shared/payouts.py:174-177`) returns `missed / outside_windows` when no window matches. The IME rules file
   lists only W1 1–7 … W4 22–28 **October**, so an upload on Oct 29–31 or any day in November gets
   "Uploaded outside the campaign weeks: not eligible". The brief describes a monthly budget in 4 weekly
   refills (an ongoing campaign), so this is likely wrong advice that makes a creator skip a valid claim.
   Suggest: no matching window inside the campaign period → `unknown` ("weeks not defined for this date,
   check the brief"), and generate weeks per month rather than hard-coding October dates in the rules file.
2. **Low · view counts use comma thousands in advice text** ("45,000 views ≥ 40,000"), while money uses
   "." (Rp 200.000). In an Indonesian UI "45,000" reads as 45. Use one grouping style ("." per the roadmap's
   IDR rule) for views too.

## Not verified
- `_block_advice` stall/settled/ending-soon thresholds against real view curves (no view data yet).
- Budget/FCFS state (`budget_exhausted`, `account_claims_this_month` are caller-supplied; no store yet).
