# prod e788649 post-deploy + hardening 1e83f0b (213, 214) on staging

## Prod after the e788649 deploy (read-only)
- backend 18:07:25, worker/sender/notifier 18:07:42, frontend/pot 18:07:53 UTC; all riftstorm-* restarts=0 (postgres untouched, up since 10-05). Order matches the stated one.
- `/docs`, `/redoc`, `/openapi.json` → 404 on :8000; `/health` and `/api/env` 200; unauthenticated `/api/jobs` via nginx 401; index 200; nginx has `@backend_updating`.
- journald: `journalctl CONTAINER_NAME=riftstorm-backend` returns the backend's lines. (Postgres still json-file until recreated, as announced.)
- Backend log since deploy: 2 hits for "error" = `AI: FAILOVER task=edit_moments gemini -> claude` (Gemini 503 "high demand", the R-22 failover working), not a defect.

## 213 (L8) keyframes — PASS
CSSOM scan of 25 keyframes on staging at 1280 and 390: none animates a non-compositor property (before: 8 used background-position/box-shadow); `analyzeGlow`, `shine`, `sweep`, `flow` are gone. Not visually compared (shimmer/glow look) with a real running job.

## 214 (L9) desktop sheets — PASS
Settings opened 4× at 1280: 0 frames > 34 ms each time, worst 33 ms (before 8 frames, worst 67 ms). `backdrop-filter` is `none` on the backdrop and sheet at 1280 and still `blur(8px) saturate(1.2)` on the backdrop at 390. 390 also 0 frames > 34 ms.

## Findings
None.

## Not verified
Visual look of the new shimmer/glow with a live running job; light-vs-dark rendering of the sheets without blur by eye.

Merge: OK for 213 and 214.
