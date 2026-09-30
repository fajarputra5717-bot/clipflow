# 017 — Disk retention + guards (R-14)
Date: 2026-09-30 · Commit: see `git log --grep R-14` · Files: worker.py, main.py, shared/settings.py, index.html

## What changed
- Settings: `DISK_SPACE_MIN_MB` (2048), `RETENTION_DAYS_INTERMEDIATE` (3), `ORPHAN_SWEEP_DRY_RUN` (true); new
  "Storage" group in the Settings sheet.
- Guards: `ensure_disk_space(stage, need_mb)` raises `DiskSpaceError` with a clear message. Called before the download
  (need = 2 × the `yt-dlp -j` pre-flight size: video+audio parts coexist until the merge), before AV1 normalization
  (need = source size), at the start of every `render_vertical()` and `apply_watermark_overlay()`.
- `POST /api/jobs` → **HTTP 507** with a message when free space is below the reserve. `GET /api/system/disk` →
  free/total/min/ok; the Settings sheet shows a disk meter (red below the reserve). Badge v2.1111.
- Idle-time sweeps from `main()` (at most every 30 min):
  - retention: deletes the download/normalized copy, audio and Submagic clean plates, **per source video**, only when
    every job on that source is terminal, every candidate is terminal and not busy at Submagic, and nothing changed for
    `RETENTION_DAYS_INTERMEDIATE` days; marks the source `purged` (source_path NULL). Finals/thumbnails never touched.
  - orphans: files in the media dirs whose name holds no known job/candidate id and whose path no DB row references,
    older than 1 h; dry run logs only.
- `delete_job` now deletes the job's `candidate_versions` rows (no FK cascade; they were left orphaned).
- A re-render on a purged source fails with "removed by disk retention …; re-import" instead of `Path(None)`.

## Decisions & trade-offs
- The per-video size pre-flight runs in the worker, not the API: the backend image has no yt-dlp/Deno, and CLAUDE.md
  keeps network/long work out of request handlers. The API's 507 covers "already below the reserve".
- Eligibility by source video: `source_videos` is unique per URL and shared by jobs, so a per-job check could delete a
  download another (still editable) job renders from, the same class as the eligibility bug REBUILD warns about.

## Verification
- API: disk endpoint; reserve set to 99,999,999 MB → POST /api/jobs 507 with message, no job row; reset to default.
- Worker (in container): pre-flight 192.4 MB vs ~193 MB real download; guard raised before any file was written.
- Retention fixtures: shared source with one job 1 day old → nothing deleted; source with a candidate in review →
  nothing deleted; both jobs >3 days + terminal → download/audio/clean plate deleted, final + thumbnail kept, source
  `purged`. Orphan sweep: dry run logs, live run deletes a 2 h old orphan, keeps a <1 h file and referenced files.
- Playwright: Settings sheet shows "346.3 GB free of 390.7 GB" + reserve note and the Storage group; no console errors.
- NOT verified: a guard firing mid-render on a real job (would need a nearly full disk).
