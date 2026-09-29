# 003 — Move app folder /opt/riftstorm → /opt/clipflow
Date: 2026-09-29 · Commit: see `git log --grep "opt/clipflow"` · Files: CLAUDE.md, START-HERE.md, scripts/bootstrap.sh, scripts/backup-db.sh, /etc/cron.d/clipflow-backup (not in repo)

## What changed
- App folder is now `/opt/clipflow`. `/opt/riftstorm` is a compatibility symlink to it.
- Path updated in bootstrap.sh (`APP_DIR`), backup-db.sh (`cd` + install comment), the cron entry
  `/etc/cron.d/clipflow-backup`, CLAUDE.md and START-HERE.md. REBUILD.md, docs/tasks and
  docs/changes had no path hits; history entries are left as written.

## Why
The folder name should match the product name (ClipFlow).

## Decisions & trade-offs
- **Compose project name stays `riftstorm`** (`name:` in docker-compose.yml), so containers stay
  `riftstorm-*` and the volumes stay `riftstorm_postgres_data` / `riftstorm_whisper_cache`. Renaming the
  project would attach a new, empty DB volume.
- Stack stopped with `docker compose down` (no `-v`) before `mv`, because the bind mounts
  (`./frontend/*`, `./db/init.sql`) are resolved from the folder at `up` time.
- Symlink kept so anything still pointing at the old path (old shells, notes, the Claude Code
  project dir) keeps working. Remove it once nothing needs it.

## Schema / settings added
None.

## Gotchas for future changes
- Never "fix" `name: riftstorm` to match the folder: that means an empty database.
- Claude Code keys its per-project memory on the working directory; start it from `/opt/clipflow`.
- `docker compose` resolves relative bind mounts from `$PWD`, and Go prefers an inherited `$PWD` even when
  it is a symlink path. A shell that was in `/opt/riftstorm` produced mounts via the symlink, so
  containers were recreated with `--project-directory /opt/clipflow`. Run compose from a fresh
  `cd /opt/clipflow` (or pass `--project-directory`).

## Verification
- `docker compose down` (no -v) → `mv` → symlink → `up -d`: all 4 containers up, postgres healthy,
  `/health` → healthy.
- `riftstorm_postgres_data` has the same CreatedAt as before the move (2026-09-29T19:17:56+07:00). The public
  schema still has 7 tables. Bind mounts and the compose `working_dir` label = `/opt/clipflow`.
- `/opt/clipflow/scripts/backup-db.sh` → new dump at 19:52:34, gzip valid, 7 `CREATE TABLE`s.
  The filename is per-day, so it replaced the 19:28 dump from earlier today.
- NOT verified: the 02:30 cron run itself (path updated in /etc/cron.d; runs tonight).
