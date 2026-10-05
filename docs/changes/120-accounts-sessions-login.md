# 120 · P1.5 part 1: users, DB sessions, login page (API key → bootstrap admin) · app/auth.py, main.py, index.html, shared/settings.py, nginx

- **Tables** (`auth.SCHEMA`, in `ensure_schema()`): `users` (username lower-case, argon2id hash, role admin|member,
  active, bootstrap), `user_sessions` (sha256 of the token only, 30-day sliding expiry, ip/ua), `login_failures`,
  `server_secrets` (media-token HMAC key; never served, unlike app_settings).
- **First run:** no users → admin from env `CLIPFLOW_ADMIN_USER` / `CLIPFLOW_ADMIN_PASSWORD` (≥ 10 chars), read only
  while `users` is empty (`bootstrap=TRUE`). Both are `ENV_ONLY_KEYS`. On this box: user `admin`, password in `.env`.
- **Middleware `require_user`** (replaces `require_api_key`) resolves `request.state.user` from: session cookie
  `clipflow_session` (HttpOnly, SameSite=Lax, Secure when `X-Forwarded-Proto: https`) → `X-ClipFlow-Key` =
  `CLIPFLOW_API_KEY` = the bootstrap admin (kept until the owner confirms removal) → `?mt=` media token, now
  `exp.user_id.sig` (per user). Open: `/api/auth/login`, `/api/auth/logout`. Cookie-authed writes with a foreign
  `Origin` → 403. Helpers `current_user(request)` / `require_admin(request)`.
- **Endpoints:** `POST /api/auth/login` {username,password} (429 after 5 fails/username or 20/IP in 15 min; unknown
  users cost one argon2 verify too), `POST /api/auth/logout` (deletes the row), `GET /api/auth/me`,
  `POST /api/auth/password` (current + new; ends the user's other sessions). No signup route.
- **UI:** `#loginScreen` (mockup card, fill inputs, pill primary) replaces the API-key `prompt()`; `body.auth-locked`
  hides + inerts app shell, tab bar and island. Any 401 reopens it and retries once; signing in as another account
  reloads. Sidebar foot: username + Sign out (`data-signout`). Island and stepper unchanged.
- Not yet: ownership/scoping (part 2), per-user settings (3), API tokens (4), admin users page (5).

**Verified (nginx :80):** anon /api/jobs + unknown /api path 401; API key → `via: api_key` admin; login 200 with
`HttpOnly; SameSite=lax` cookie, session `/api/auth/me` + jobs 200; per-user mt has 3 parts; cross-origin cookie POST
403; 5 wrong logins 401 then 429; logout → 401; stored hash `$argon2id`. Harness 38 passed (+ login.spec, desktop
+ mobile); live.spec (legacy key header) passed.
