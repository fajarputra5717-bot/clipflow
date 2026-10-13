# 212 · user_sessions expiry index; /api/activity = one connection, one transaction (deep audit L11, 2026-10-14)

- **user_sessions:** prod stats (read-only): 40,671 seq scans vs 3,021 index scans on an 18-row table. EXPLAIN shows the
  token lookup seq-scans one page by the planner's choice although `token_hash` is the primary key; the expiry sweep
  on every login (`DELETE … WHERE expires_at < NOW()`) had no index at all. New `idx_user_sessions_expires`
  (auth.py schema). Throwaway Postgres with 20,000 sessions: the lookup uses `user_sessions_pkey`, the sweep a bitmap
  scan on the new index. At today's size the seq scans are expected and cheap.
- **/api/activity:** traced with Postgres `log_statement=all` (throwaway DB, no worker): every call opened 2 connections /
  2 transactions (auth middleware's lookup, then the handler's 5 queries). The audit's 15 counted staging's worker +
  notifier polling too. Now the middleware keeps its auth connection for `REQUEST_DB_PATHS` (`/api/activity`) on
  `request.state.db`, the handler takes it through `request_db(request)`, and the middleware commits + closes it on every
  exit (`require_user` → `_require_user` inside try/finally) → 1 connection, 1 transaction per poll (traced). Other routes
  are unchanged (opt-in). Checked: 200 with token and with a session cookie, 401 without/bad token, other routes OK,
  0 connections left open afterwards.
