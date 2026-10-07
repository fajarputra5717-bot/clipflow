# 158 · P3 part 2: campaign status engine (Active / Ending soon / Ended / Paused + open week) · shared/campaign_status.py, main.py

- **Why:** P3 spec part 2 + roadmap "P3 · Campaign step spec" item 2 (owner 2026-10-07).
- **`shared/campaign_status.py` (pure):** `status(rules, now)` → `{code active|ending_soon|ended|paused, label, detail,
  last_day, days_left}`; `current_week(rules, now)` → `{id, start, end, days_left}` or None. Last posting day =
  the earlier of the period end and the last week window's end (`payouts.campaign_period` / FixedThreshold
  windows), so IME is "Ended" on 29–31 Oct; ≤ 3 posting days left (today included) = "Ending soon"; paused flag
  (157) wins; open-ended campaigns (Fandra, budget) stay Active. `detail` = Lane B's
  `review_state.campaign_status` text ("Week 1 · 1 day left", "Open until the budget runs out"), so the
  Review header, the Campaign step and clip labels phrase it once.
- **API:** every campaign in `GET /api/campaigns` and `GET /api/campaigns/{slug}` carries `status` + `week`.

**Verified:** `tests/test_campaign_status.py` 4 OK on the real rules (IME W1 1 day left on 7 Oct, W2 from 8 Oct,
26 Oct ending soon 3, 29–31 Oct Ended "Ended 28 Oct", paused wins; Fandra Active through 2027, no week); all unit
files OK; prod (read-only, 7 Oct): IME Active "Week 1 · 1 day left" W1, Fandra + Motionklip Active "Open until
the budget runs out".
