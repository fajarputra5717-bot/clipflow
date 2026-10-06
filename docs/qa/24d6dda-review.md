# QA review · 24d6dda · 128 P2 part 1: posting accounts per user (Settings)
Reviewer: Lane C · 2026-10-06 · `/api/accounts/{id}` added to the ownership middleware (ACCOUNT_PATH_RE) → other users' accounts 404; list scoped. Not verified live (staging lacks 128 beyond lane-b merge; prod needs a cf_ token).
