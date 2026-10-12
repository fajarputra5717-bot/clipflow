# 190 · View pulls: Lane C's 3 Lows on 189 (2026-10-13)

- `view_pull.error_kind()`: `rateLimitExceeded` / `userRateLimitExceeded` / 429 / 5xx = transient (next run), not
  'quota' (which stops pulls for the whole Pacific day; only quotaExceeded / dailyLimitExceeded do). A 400/403 is 'key'
  (admin alert "key refused") only for keyInvalid / keyExpired / accessNotConfigured / ipRefererBlocked or an
  "API key" message; any other 4xx = 'request' (logged on the run, no alert).
- Publish panel: a YouTube post whose views came from a pull shows "· from YouTube" and a hint that pulls continue
  after a claim/payment and replace a typed number at the next pull (shown only once a pull has updated the post).
- Tests: unittest view_pull (rate limit, key 400, other 400); publish.spec YouTube auto-views hint.
