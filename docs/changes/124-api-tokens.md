# 124 · P1.5 part 4: per-user API tokens (hashed) for scripts; CLIPFLOW_API_KEY kept as the admin token · app/auth.py, main.py, index.html

- **Table `api_tokens`** (id, user_id → users ON DELETE CASCADE, name, sha256 `token_hash` UNIQUE, `prefix` = first
  10 chars for display, created_at, last_used_at touched at most every 5 min). Token = `cf_` + 32 random bytes
  (urlsafe); the plaintext is returned once by the create call and never stored. Max 20 per user.
- **Auth:** the middleware accepts `cf_…` in `X-ClipFlow-Key` or `Authorization: Bearer` → that user
  (`via: api_token`); a disabled user's tokens stop working; an unknown `cf_…` is 401 (no fall-through to the legacy
  key). Ownership/scoping apply exactly as for a session. Header-based, so no Origin check; CORS allows `Authorization`.
  `CLIPFLOW_API_KEY` still maps to the bootstrap admin until the owner confirms its removal.
- **Endpoints:** `GET/POST /api/auth/tokens`, `DELETE /api/auth/tokens/{id}` (own only, else 404). Managed from a
  browser session or the legacy key only: a token can't list or mint tokens (403).
- **UI:** Account sheet → "API tokens": name + Create, plaintext shown once with Copy (hidden again when the sheet
  reopens), list (name, prefix…, created, last used), two-step Revoke (no browser dialog).

**Verified:** production (read-only): token list via the legacy key `{"tokens":[]}`, bogus `cf_…` in either header
401, anonymous list 401, legacy key 200, table present. Harness 46 passed (+ tokens.spec). Create/use/revoke and
cross-user token checks run on staging with the other write checks (staging-only rule).
