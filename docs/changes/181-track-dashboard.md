# 181 · P3 part 8 — Track dashboard (2026-10-09)

- `shared/track.py` (pure, `tests/test_track.py`): the caller's posted/claimed/paid clip_posts → tiles (views, paid,
  expected, claimed vs paid, posts at cap), by campaign, by platform, top 10 clips by views. Per post: paid → paid_rp,
  claimed → stored expected_rp, posted → `payouts.payout_for` at its latest views ("If claimed now"); at cap =
  `payout_for ≥ payouts.max_payout`. Non-IDR shows "$15.00 (~Rp 247.500)" (`payouts.format_with_idr`), totals in IDR
  via `payouts.to_idr`; a currency without a rate is skipped and listed. Nothing is computed in index.html.
- `GET /api/track` (owner-scoped). Stepper step 8 live (`#track`, `#trackSection`, `loadTrack()`/`renderTrack()`).
  Phone pill now shows 7 steps (only Auto-import is "Coming in P3"): no gaps, 4 px side margins, active label 12 px
  ≤ 52 px — every target stays 44 px.
- Views come from each post's latest `views` (manual now; P5 fills them automatically). Prod 2026-10-09: no posted
  clips yet → empty state.
- Tests: track.spec (tiles, tables, top clips incl. USD + At cap, empty state, no horizontal scroll), shell/publish
  pill updates. UI 192 passed; unittest track + payouts OK.
