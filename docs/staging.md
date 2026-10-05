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

## Commands

```bash
scripts/staging.sh reset     # fresh DB from the newest /data/backups dump, empty /data-staging, build + start
scripts/staging.sh up        # build (lane-b code) + start, keeps the DB
scripts/staging.sh down      # stop (keeps the DB volume)
scripts/staging.sh status    # containers + URLs
scripts/staging.sh logs worker          # last 80 lines (backend|worker|frontend|postgres)
scripts/staging.sh rebuild worker       # after changing worker/ or shared/
scripts/staging.sh psql
```

Frontend changes need no rebuild (directory mount); hard-refresh :8080. The API key is production's
(`.env.staging` is generated from `/opt/clipflow/.env`, gitignored, mode 600).

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
