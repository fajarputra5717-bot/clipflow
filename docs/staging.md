# Staging stack (lane B)

A full copy of ClipFlow for testing editor work, run from the **lane-b worktree**
(`/opt/clipflow-lane-b`). Separate compose project `clipflow-staging`: its own containers, network
and Postgres volume (`clipflow-staging_staging_pg`). **Production (`riftstorm-*`,
`riftstorm_postgres_data`) is never touched.**

| | Production | Staging |
|---|---|---|
| UI | http://\<host\>:80 | **http://\<host\>:8080** |
| API | 127.0.0.1:8000 | **127.0.0.1:8001** |
| DB | riftstorm_postgres_data | clipflow-staging_staging_pg (restored from `/data/backups`) |
| Media | /data (rw) | /data **read-only** at /data + **/data-staging** (rw, `DATA_ROOT`) |
| Worker | all CPUs | **2 CPUs** (`cpus: 2`), `restart: "no"` everywhere |

Merged with main at least daily, so staging always runs **main + the editor work**.

## Commands

```bash
scripts/staging.sh reset     # fresh DB from the newest /data/backups dump, empty /data-staging, build + start
scripts/staging.sh up        # build (lane-b code) + start, keeps the DB
scripts/staging.sh down      # stop (keeps the DB volume)
scripts/staging.sh status    # containers + URLs
scripts/staging.sh logs worker          # last 80 lines (backend|worker|frontend|postgres)
scripts/staging.sh rebuild worker       # after changing worker/ or shared/
scripts/staging.sh admin        # re-apply the staging admin password
scripts/staging.sh psql
```

Frontend changes need no rebuild (directory mount); hard-refresh :8080.

## Login (P1.5)

Staging restores production's users, but **every admin account gets a staging-only password**: user
`admin`, password = `STAGING_ADMIN_PASSWORD` in `/opt/clipflow-lane-b/.env.staging` (root-only, mode 600,
gitignored; generated once and kept across resets). Production's `CLIPFLOW_ADMIN_PASSWORD` is never
copied; admin sessions are dropped on reset. `scripts/staging.sh admin` re-applies it.
Members keep their production passwords; QA can add staging-only members in the staging DB.

**No production credential works on staging** (QA Low): `reset` and `up` delete every session, API token and
login failure restored from production; the session cookie is `clipflow_staging_session` (main 140:
`CLIPFLOW_ENV=staging` in `.env.staging`; production's `clipflow_session` is ignored on :8080); production's
`CLIPFLOW_API_KEY` no longer authenticates anywhere (main 127). Scripts: sign in, then use a per-user token
(Account → API tokens) or the session cookie. A "STAGING" strip sits above every screen, login included
(`GET /api/env` → `{"env": "staging"}`, open, no secrets).

## What the reset does

1. `docker compose -p clipflow-staging down -v`: removes the **staging** volumes only (the Whisper cache
   `riftstorm_hf_cache` is external and mounted read-only, so it is never removed).
2. Empties `/data-staging`, recreates its folders, copies `/data/watermarks` and `/data/thumbnails`
   (stored as paths relative to `DATA_ROOT`). Absolute paths in the DB (`/data/downloads/…`,
   `/data/final/…`) are read from the read-only production mount, so sources and finals are visible
   without copying 15 GB.
3. Restores the newest `/data/backups/clipflow-*.sql.gz` into the staging Postgres.
4. **Parks in-flight work**: running/queued jobs → `cancelled`, running candidates → `failed`, active
   Submagic states → `failed` (message "parked by staging reset"), so the staging worker never
   reprocesses production's queue.
5. Starts everything.

## Safety

- `.env.staging` strips Telegram, Submagic, YouTube and Runway keys: staging can't post, bill or alert.
  AI keys (Gemini/Claude) stay so analysis and utility calls work.
- No notifier and no n8n in staging.
- Sweeps can't delete: `/data` is read-only, `ORPHAN_SWEEP_DRY_RUN=true`,
  `RETENTION_DAYS_INTERMEDIATE=36500` (and any DB override of those two is deleted on reset).
- New renders land in `/data-staging/{previews,final,…}` and are gone after the next reset.

## UI tests against staging

`CLIPFLOW_UI_BASE=http://localhost:8080 tests/ui/run.sh` runs the Playwright harness (mocked `/api`)
against lane-b's frontend. Plain `tests/ui/run.sh` targets production's :80, which doesn't have lane-b
pages yet, so new specs fail there until Lane A merges.
