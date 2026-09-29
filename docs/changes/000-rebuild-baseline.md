# 000 — Rebuild baseline after VM loss
Date: 2026-09-26 · Commit: (initial) · Files: all

## What changed
- Original VM crashed; disk unrecoverable; no git remote existed. All work after UI v2.1100 was lost.
- Repo recreated from the last surviving copies of main.py / worker.py / index.html (v2.1100).
- Infrastructure rebuilt: docker-compose.yml, Dockerfiles, requirements, nginx conf, .env.example, db/init.sql.

## Why
Server loss. See REBUILD.md for everything that must be rebuilt, in order.

## Decisions & trade-offs
- All IDs are TEXT (gen_random_uuid()::text default): the code joins clip_candidates.id to
  candidate_versions.candidate_id (TEXT) and inserts str(uuid4()).
- torch installed from the CPU-only index (no GPU; avoids ~2GB of CUDA wheels).
- Deno added to the worker image: yt-dlp needs a JS runtime for YouTube.
- nginx uses Docker's resolver with a variable proxy_pass (fixes the old stale-IP 502).
- Frontend uses directory bind mounts, not single-file mounts (atomic-save detach gotcha).
- Backend port bound to 127.0.0.1 only; UI/API go through nginx on :80.

## Schema / settings added
db/init.sql base tables: app_settings, source_videos, jobs, clip_candidates, rendered_clips.
Later columns stay in ensure_schema().

## Gotchas for future changes
Do not add columns to init.sql: it only runs on an empty volume. Use ensure_schema().

## Verification
- Verified: every ensure_schema() statement and all 73 literal SQL statements in main.py/worker.py
  PREPARE without error against init.sql on Postgres 16; the dynamic update helpers' columns exist;
  `docker compose config` valid; py_compile and node --check pass.
- NOT verified: image builds (no PyPI access where this was prepared), a real end-to-end job,
  Postgres 17 specifically (16 was used for the check).
