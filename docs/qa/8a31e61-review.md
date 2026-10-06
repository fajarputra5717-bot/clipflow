# 8a31e61 (145) P2.5 S1 suggested posting times per user, WIB — QA 2026-10-07

Deploy: prod backend/worker/notifier restarted 2026-10-06 21:50Z, 5/5 riftstorm-* running, 0 restarts.
UI suite (git-served main): 93 passed, 0 failed, 5 skipped (incl. posting-times.spec.js).
Code check (host python, shared/schedule.py):
- normalize: "9:05" becomes 09:05, duplicates are dropped, and 24:00, unknown platforms, non-object and non-list
  values are rejected with user-facing 400s. POSTING_TIMES is in USER_SETTING_KEYS (per user, members allowed).
- next_slots: starting 27 Oct 20:00 WIB with 21:00 already taken, it gives 28 Oct 12:00/19:00/21:00 and then stops,
  because 29 Oct+ is outside the IME W1–W4 window. That's correct.
Bugs:
1. Low: index.html:1305 .ptime-chip remove button is 28×28 px, below the --hit 44 px token. Hard to tap on 390.
Not verified: pytest tests/test_schedule.py (no pytest on the host); live member PUT on staging (staging is
lane-b 53f34b9, before 145); next_slots isn't called by any endpoint yet (S1 is settings only).
