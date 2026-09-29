# 002 — API key auth + CORS lock-down (R-03)
Date: 2026-09-29 · Commit: see `git log --grep R-03` · Files: main.py, index.html, CLAUDE.md

## What changed
- Every `/api/*` request requires `X-ClipFlow-Key` = env `CLIPFLOW_API_KEY`, compared with
  `secrets.compare_digest`. Uniform `401 {"detail":"Unauthorized"}`, also for unknown `/api` paths.
  `/health` and `/` stay open.
- CORS: `allow_origins` from env `CORS_ALLOWED_ORIGINS` (comma list, `*` ignored), no credentials,
  explicit methods and headers (was `*` + credentials).
- Media: `GET /api/media-token` → `{token, expires_at}`. The 5 GET file routes (candidate preview /
  render / thumbnail / thumbnail-options/N, watermark file) also accept `?mt=<exp>.<hmac-sha256>`.
- Frontend: key prompted once per session (sessionStorage), sent from `api()` and both upload calls
  (now `authFetch()`). A 401 re-prompts once, shared across concurrent calls. `mediaUrl()` appends the token to
  every `<img>`/`<video>`/download URL. Badge v2.1101.

## Why
The API was open with `allow_origins=["*"]`: anyone on the LAN could delete jobs, spend Gemini
credits and trigger billable Submagic exports.

## Decisions & trade-offs
- **Middleware instead of a FastAPI dependency** (the spec's wording): a dependency only runs on
  matched routes, so unknown paths would 404 and leak which routes exist. The middleware covers every
  `/api/*` path.
- **File auth = signed query token**, not open GET routes: clips are unpublished content. The token is
  read-only, limited to those 5 paths and GET, and derived from the API key (rotating the key revokes
  it). Bucketed to 12 h so URLs don't change on each re-render (a changed `<video src>` restarts
  playback). Trade-off: a leaked media URL can read media for up to 24 h. The key itself never goes in a URL.
- Fail closed: empty `CLIPFLOW_API_KEY` → every `/api/*` returns 401, plus a startup log line.
- `/docs` and `/openapi.json` left on. nginx only proxies `/api/` and `/health`, so they're
  reachable only on 127.0.0.1:8000 from the VM.
- Not done here: rate limiting (TASKS-2 T2 bullet). REBUILD R-03 doesn't list it, and it belongs to
  TASKS-4-SECURITY T4 (TODO).

## Schema / settings added
None. Env: `CLIPFLOW_API_KEY`, `CORS_ALLOWED_ORIGINS` (both already in .env.example, env-only).

## Gotchas for future changes
- New file-serving GET route → add it to `MEDIA_PATH_RE` and wrap its URL in `mediaUrl()`, or the image/video 401s.
- No bare `fetch()` in index.html: use `api()` / `authFetch()`.
- Keep CORS `add_middleware` after the auth middleware; otherwise preflights get 401.
- Changing CORS_ALLOWED_ORIGINS or the key needs `docker compose up -d backend` (read at startup).
  Users then get re-prompted on their next 401.

## Verification
- curl via nginx: no key / wrong key → 401; right key → 200; unknown /api path → 401 without key and 404 with it;
  DELETE, PUT and multipart upload without a key → 401; direct :8000 → 401; /health → 200.
- CORS: preflight from the configured origin → 200 with X-ClipFlow-Key allowed; foreign origin → 400 without
  allow-origin. The 401 to the allowed origin carries allow-origin.
- Media token: 200 for a watermark file. 401 for tampered sig, forged exp, correctly-signed expired
  token, a token on /api/jobs or /api/settings, and POST/DELETE with a token. Token stable across calls, ~23 h left.
- Headless Chromium (Playwright): wrong key → one re-prompt → all 200s; reload → no prompt; new
  session → one prompt; settings panel loads; UI watermark upload works; its media-token `<img>` URL → 200
  and renders. No page errors. Test assets and settings rows deleted.
- NOT verified: `<video>` preview/render playback and Range requests with the token (no candidate
  exists; Gemini 503 in R-01). Safari. Thumbnail upload endpoint (needs a candidate). Behaviour when the
  hourly token refresh crosses a 12 h bucket in a long-lived tab. HEAD on file routes returns 405
  (pre-existing, `@app.get` only).
