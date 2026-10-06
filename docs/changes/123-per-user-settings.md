# 123 · P1.5 part 3: per-user settings; global settings admin-only; worker reads the job owner's · shared/settings.py, main.py, worker.py, index.html

- **User-level keys** (`USER_SETTING_KEYS`, shared/settings.py): DEFAULT_SUBTITLE_STYLE/FONT/SIZE,
  FULLFRAME_CAPTION_Y, SUBTITLE_SEAM_GAP, WATERMARK_WIDTH/OPACITY/POSITION_Y, ACTIVE_WATERMARK_ID, HASHTAGS. Stored
  in `user_settings (user_id, key, value)`. Precedence for them: **user → app_settings (admin's house default) →
  env → default**; `RuntimeSettings.resolve(key, default, user_id)` (source `user`), per-user 5 s cache.
  `USER_ONLY_KEYS` (ACTIVE_WATERMARK_ID) never fall back to a global value: it names an owned asset.
- **Migration:** the global ACTIVE_WATERMARK_ID row moves to the bootstrap admin's user settings (startup, once).
- **API:** `GET /api/settings` → members get only user-level keys (own effective values); admin gets all, each
  entry with `scope` user|global. `PUT`: user keys → the caller's `user_settings` ("" = back to the default);
  any global key from a member → **403**; ACTIVE_WATERMARK_ID must be the caller's asset (404).
  Watermark list/upload (first own asset auto-activates)/activate/delete use the caller's active id.
  create_job's subtitle defaults + snapshotted positions and generate-description's HASHTAGS read the caller's.
- **Worker:** `run_as_owner(job_id, fn, task)` wraps every claimed task in `main()`; a `ContextVar` makes
  `setting()/setting_int()/setting_float()` resolve user-level keys for the job's owner (no call-site changes).
  `resolve_watermark_path()` uses the owner's active asset and only one the owner owns.
- **UI:** the Settings sheet renders only returned keys (member: user keys only); source labels Yours / House
  default / From .env / Default, plus "your jobs" / "all users" for admins.
