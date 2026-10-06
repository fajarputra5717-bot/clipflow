# 127 · Shared CLIPFLOW_API_KEY removed (owner decision); per-user cf_ tokens only · main.py, app/auth.py, shared/settings.py, .env.example, scripts/bootstrap.sh, tests/ui

- Owner 2026-10-06 ("P1.5 gate PASS", owner's message; Lane C's `docs/qa/gate-P1.5.md` was still pending, its member
  e2e still running): the legacy admin key is gone. `X-ClipFlow-Key` /
  `Authorization: Bearer` now accept only per-user `cf_…` tokens (any other value → 401). `bootstrap_admin()` and the
  `api_key` principal are removed; tokens are managed from a signed-in session only.
- `ENV_ONLY_KEYS` no longer lists `CLIPFLOW_API_KEY`. `.env.example` documents `CLIPFLOW_ADMIN_USER` /
  `CLIPFLOW_ADMIN_PASSWORD` instead; `scripts/bootstrap.sh` generates the admin password (no API key).
- `live.spec.js` uses `CLIPFLOW_API_TOKEN=cf_…` (Bearer). START-HERE, tests/ui/README and CLAUDE.md updated.
- The value still sitting in `.env` is now unused (owner may delete the line; staging's `.env.staging` is derived
  from it).

**Verified (prod):** old key in `X-ClipFlow-Key` and as Bearer → 401, anonymous 401; admin session login 200,
`/api/jobs` 200, token list 200. Harness 66 passed.
