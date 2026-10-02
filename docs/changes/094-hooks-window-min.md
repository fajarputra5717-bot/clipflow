# 094 · Hook analysis window minimum 10 minutes (P0) · main.py, worker.py

A 1-minute window means 120–240 AI calls for a 2-hour video. `PUT /api/settings` now rejects
`HOOKS_WINDOW_MINUTES` < 10 (`HOOKS_WINDOW_MIN_MINUTES`; 400 "…at least 10 minutes…"), on top of 084's
overlap < window check. The worker clamps `transcript_windows()` to ≥ 600 s with a log line, for values set
via env/DB directly.

**Verified:** PUT 5 and 1 → 400; clearing the key → 200 (default 30); worker with a 60 s window logs the
clamp and makes 12 windows for a 2-hour transcript instead of 120.
