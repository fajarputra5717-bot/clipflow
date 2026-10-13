# 209 · Logs survive redeploys; deploy gaps are absorbed (deep audit M6, 2026-10-14)

- **Logs:** the compose `x-logging` anchor moves from `json-file` (20 MB × 3, but deleted with the container on every
  recreate, so a 7-day log review was impossible) to `journald` (`tag: {{.Name}}`). The host journal is persistent
  (`/var/log/journal`, 48 MB used, journald's default cap = 10 % of the disk / max 4 GB). `docker compose logs` still
  works; history across deploys: `journalctl CONTAINER_NAME=riftstorm-backend --since "7 days ago"`. A service picks it
  up when it is next recreated (staging compose unchanged).
- **Deploy gap:** measured on staging, a backend recreate leaves ~1.5 s of nginx 502 (stop → start; `/health` 200 again
  after 2.0 s). The 10-12 nginx "connection refused" lines were these gaps during deploys. nginx now answers `/api/` 502/504
  with a JSON 503 + `Retry-After: 5` (`@backend_updating`) instead of its HTML page, and the frontend's
  `fetchThroughDeploy()` (inside `authFetch`) retries reads (GET/HEAD) on 502/503/504 or a network error after 1, 2.5 and
  5 s before anything says "ClipFlow is updating…"; writes are never retried (no double submit). A second backend for
  blue/green isn't worth it for a 1.5 s gap that the retry window (8.5 s) covers.
- Spec: load-errors.spec.js "a read that hits a deploy (502/503) is retried quietly and loads; a write is never resent".
