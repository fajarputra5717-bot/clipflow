# 145 · P2.5 S1: suggested posting times per user (WIB) + shared/schedule.py · settings, main.py, index.html

- **Why:** first part of P2.5 Schedule (spec docs/tasks/P3-campaign-track.md § P2.5); owner 2026-10-07: start S1
  now, S2–S4 after Lane C's gate-P2.md PASS.
- **Setting:** `POSTING_TIMES` in `DEFAULT_SETTINGS` + `USER_SETTING_KEYS` (user → app → env → default), JSON
  `{platform: ["HH:MM", …]}` in WIB, keys = `rule_checks.PLATFORM_LIMITS`. Defaults (owner-approved): tiktok
  12:00/19:00/21:00, instagram 11:30/19:30, youtube 17:00/20:00, facebook 12:00/19:00.
- **`shared/schedule.py` (pure):** `normalize_posting_times()` (strict: known platforms, 24 h HH:MM, sorted, deduped,
  ≤ 8 per platform; ValueError = user-facing message), `parse_posting_times()` (lenient read with fallback),
  `next_slots(times, platform, after, taken, *, n=3, rules=None, days=14)` → UTC slots strictly after `after`,
  skipping taken minutes and, with campaign rules, slots outside the posting window (`payouts.window_problems`:
  period + IME weeks). WIB is fixed UTC+7 (no DST). S2 uses it for "Approve & schedule".
- **API:** `PUT /api/settings` validates + stores the normalised JSON (400 with the message); `""` = back to the
  default. Members save their own (user key).
- **UI:** Settings → Posting times (under Posting accounts): one row per platform, time chips with ✕, a time input +
  Add, Save times (enabled when changed), Reset to defaults.

**Verified:** `tests/test_schedule.py` 11 OK (real IME rules: 28 Oct 21:00 is the last slot, 29–31 Oct skipped;
Fandra open-ended, starts 30 Sep); UI suite 93 passed (new `posting-times.spec.js`, desktop + mobile).
