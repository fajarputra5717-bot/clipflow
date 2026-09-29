# 060 — Security audit 001 (TASKS-4-SECURITY T1)
Date: 2026-09-29 · Commit: see `git log --grep "audit-001"` · Files: docs/security/audit-001.md · No code changed

## What changed
Added the threat model and findings report `docs/security/audit-001.md` (ASVS L1 + OWASP Top 10 2021).

## Why
TASKS-4-SECURITY requires an audit before any hardening. R-03 already landed auth + CORS, so the report records
those as closed and rates the rest against the real exposure: LAN + Tailscale, no public ingress.

## Decisions & trade-offs
- Severity is rated for this deployment. Every open finding needs the API key, so none is High.
- The `.env.swp` leak is recorded as closed (purged, keys rotated). No secret values are in the report.
- Only unauthenticated probes ran live (lane B may not read `.env`). Everything else is marked "verified by code reading".

## Gotchas for future changes
- T3 priorities from the report: F4 (yt-dlp `--` + host allowlist), F5 (drop the raw-bytes upload fallback), F9 (containment check).
- T4: the daily cap on `submagic/export` covers most of the money risk (F6).

## Verification
Probes against 127.0.0.1:8081: 401 on every /api path tried (incl. unknown, DELETE, 50 MB POST, forged media token);
CORS preflight from a foreign origin → 400 without ACAO; /docs and /openapi.json → SPA fallback. OSV lookup of both
images' `pip freeze`. Log grep for key patterns → 0 hits.
