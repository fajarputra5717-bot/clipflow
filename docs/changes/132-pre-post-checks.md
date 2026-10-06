# 132 · P2 part 4: pre-post checks on Publish rows (warn, never silently block) + "not eligible" posts · shared/payouts.py, main.py, index.html

- **One source: `shared/payouts.py`** (131) + Lane A's eligibility section: `window_problems(rules, model, when)` =
  campaign `period` (Fandra from 30 Sep; open end) + FixedThreshold week windows (IME W1–W4 = 1–28 Oct WIB;
  29–31 Oct and later are outside); `cap_problem(model, used, handle, platform)` = IME 2 eligible posts per platform
  account per WIB calendar month. Platform length = `rule_checks.PLATFORM_LIMITS` (e.g. "Over 90 s for Facebook Reels").
- **Row checks** (`GET /api/publish-queue` → `checks[]`, `account_usage{}`):
  - `block` (red) = exactly the clip-level failures that block Approve (`rule_checks` blocking chips: length,
    hashtags, watermark). Mark posted is disabled on the row, and `POST /api/posts` (posted) / planned→posted
    answer 409 "Fix before posting: …".
  - `warn` (amber) = outside window / before start / after end, cap reached per account (counted from this user's
    eligible, non-dropped posts of that campaign in the WIB month), this platform's length.
- **Mark posted still works with warnings:** the post is stored `eligible = false` + `ineligible_reason` (new
  clip_posts columns) — computed server-side at posting time for the chosen account and posted_at; the form previews
  "Will be recorded as not eligible: …" and updates when you switch account; the account picker shows "2/2 this
  month (cap reached)". Posted rows show a "Not eligible" badge + reason. Ineligible posts don't count toward the cap.
  No campaign → no eligibility (length is a heads-up only).

**Verified:** payouts tests 25 OK (21 Lane B + 4 eligibility on the real rules: IME 6 Oct ok, 28 Oct 23:59 ok,
29/30/31 Oct outside, 28 Oct 23:30 UTC = 29 Oct WIB outside; Fandra 29 Sep before start, 30 Sep ok, open end; cap
2/2); posts tests 13 OK; harness 79 passed (+ red disables Mark posted, warnings, per-account preview, post allowed);
prod read-only: 61 rows, 0 checks today (inside W1, after Fandra start, no accounts, all approved); DB-free
`_post_warnings` on prod code: IME 30 Oct FB 104 s @cap → window + cap + length; Fandra 29 Sep → before start.
Posting with warnings on real data = a write → staging.
