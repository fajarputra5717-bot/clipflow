# Payout models + claim advice (lane B, task 4) — number assigned by Lane A at merge

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
