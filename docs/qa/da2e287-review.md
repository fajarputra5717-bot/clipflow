# QA review · da2e287 · 120 P1.5 part 1: users, DB sessions, login page; CLIPFLOW_API_KEY → bootstrap admin
Reviewer: Lane C · 2026-10-05 · deployed on production (unauthenticated /api/* → 401; 1 admin, 1 session).
Checked (code): argon2 hashes; session tokens random, stored **hashed** (`token_hash`), DB expiry + sliding refresh,
expired rows purged, logout deletes the row, password change revokes other sessions; cookie HttpOnly + SameSite=Lax
(+ Secure on HTTPS); writes require an allowed Origin (CSRF belt); `CLIPFLOW_API_KEY` compared with
`secrets.compare_digest` and mapped to the bootstrap admin; bootstrap admin from env only while `users` is empty;
login rate limit in DB (5 fails/username, 20/IP per 15 min); client IP from nginx's `X-Real-IP` (nginx overwrites it,
not spoofable); media tokens per user (HMAC of user + expiry, constant-time check); no signup route.
## Findings
1. **Low · username lockout DoS**: anyone can lock a known username for 15 min with 5 bad passwords (inherent to
   per-user limits; consider exponential backoff instead of a hard lock, or IP+user pairs).
2. **Info** · ownership/404 isolation is part 2: `qa-multiuser.spec.js` runs once a second user and ownership exist.
Not verified: login/logout/password flows live (QA has no member account yet; Lane B's `login.spec.js` covers the UI).
