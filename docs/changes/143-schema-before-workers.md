# 143 · Deploy order made structural: backend migrates first; worker + notifier wait for service_healthy · main.py, docker-compose.yml

- **Why:** twice a deploy started the worker before the backend had created a new table (141: `telegram_sends`
  UndefinedTable → one crash + restart; earlier columns raced the same way).
- **Now:** `SCHEMA_READY` is set after `ensure_schema()` (+ bootstrap admin) and a check that the newest table exists;
  `/health` returns 503 `{"status":"migrating"}` until then. Compose: backend `healthcheck` = python urllib GET
  /health (5 s interval, 30 retries, 20 s start period); worker and notifier `depends_on: backend: {condition:
  service_healthy}` (plus postgres as before). The worker-side UndefinedTable guards from 141 stay as a second line.
- CLAUDE.md deploy rules: schema only in the backend; new readers of app tables get the same depends_on.

**Verified (prod):** `docker compose up -d --force-recreate backend worker notifier` (idle) → compose "Waiting" →
backend Healthy 00:21:08.50 WIB → worker/notifier Started 00:21:08.85; log "schema ready: True"; no tracebacks;
/health healthy. Staging's compose (lane-b `docker-compose.staging.yml`) needs the same healthcheck/depends_on.
