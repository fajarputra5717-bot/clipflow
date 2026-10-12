# 183 · P3 part 7 — Auto-import via source_watch (2026-10-12)

- `shared/auto_import.py` (pure, `tests/test_auto_import.py`): `channel_key()` (one spelling per channel, handles
  lowercased), `watchable(rules)` (the campaign's YouTube `sources`), `skip_reason()` — campaign paused/ended, under
  AUTO_IMPORT_MIN_MINUTES (5), uploaded > 12 h before the switch went on (`enabled_at`), before the campaign start;
  no upload time (past the RSS window) is skipped only when the channel's seen-list is stale (no good check in 24 h).
- Tables (backend `ensure_schema`, readiness now checks `source_imports`): `source_watches` (user × campaign × channel,
  `enabled_at`), `source_channels` (the shared check queue, one row per channel, no user data, like `source_videos`),
  `source_imports` (per user, UNIQUE (user_id, url), status found|imported|skipped|failed + reason, job_id).
- Worker: idle branch `maybe_check_sources()` (≤ 1 claim / 30 s, after renders/analysis/Submagic): `claim_source_channel()`
  (FOR UPDATE SKIP LOCKED; a `checking` row older than 15 min is reclaimable) → `ensure_disk_space` (low = postpone,
  nothing marked seen) → `source_watch.check_channel()` (yt-dlp through shared/ytdlp, first check = baseline, no backlog)
  → per user the first watch that accepts a video records `found`, else `skipped` + reason. Next check after
  AUTO_IMPORT_INTERVAL_MIN (15). One check per channel serves every user who watches it.
- Backend: `create_job()` → `create_job_for(req, user)`, the ONE job-creation path. `run_import_loop()` (daemon thread,
  every 15 s, short DB work) turns `found` rows into jobs owned by the watch's user, with the campaign's layout /
  clip count / language (`default_language` or auto); already has a job with the URL → skipped "Already imported";
  507 → waits for disk; 400 (e.g. paused) → skipped; other errors retry ×3 then failed.
- API: `GET /api/auto-import` (visible campaigns with sources → channels with `watched` + "checked 4 min ago" line,
  last error; the caller's 30 latest imports with label + badge), `PUT /api/auto-import/watch {campaign, channel,
  enabled}` (404 invisible campaign, 400 not a source, 409 switching on an ended/paused campaign; on = check soon).
  `/api/activity` kind `source_check` while a watched channel is checked (island, indeterminate; tap → `#import`).
- UI: stepper step 2 live (`#import`, `#importSection`, `loadImport()`/`renderImport()`, `.ai-switch` role=switch,
  44 px hit area). Every step is live now, so phones show all 8; ≤ 440 px the active step is icon-only (accent pill,
  name in aria-label + page title) because 8 × 44 px + a label don't fit 390. Settings → Auto-import (2 keys).
- Tests: unittest auto_import; auto-import.spec (switch PUT, ended locked, imports, empty state), shell/publish/account
  pill updates, touch tour includes #import. UI 198 passed.
