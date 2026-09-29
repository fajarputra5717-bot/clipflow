# 001 — Runtime settings: one precedence rule (R-02)
Date: 2026-09-29 · Commit: see `git log --grep R-02` · Files: shared/settings.py, main.py, worker.py, index.html, CLAUDE.md

## What changed
- New `shared/settings.py` → `RuntimeSettings`: **DB (app_settings) → env → default**, first
  non-empty wins, 5 s in-process cache. Worker `setting()` and backend `runtime_setting()` both
  delegate to it (backend used to be env-wins; worker re-queried the whole table on every call).
- `DEFAULT_SETTINGS` + `SECRET_SETTING_KEYS` moved there, so both files share the whitelist and defaults.
- Dead settings wired: the worker had import-time `os.getenv` constants, so the UI had no effect on
  PREVIEW_WIDTH, CLIP_COUNT, CLIP_TARGET/MIN/MAX_DURATION, FACE_DETECTION_SAMPLE_COUNT,
  FACE_CONFIDENCE_THRESHOLD, FACE_ZOOM_RATIO, FFMPEG_(PREVIEW_)PRESET/CRF, WATERMARK_WIDTH/OPACITY,
  GEMINI_MAX_ATTEMPTS (gemini_call ignored the DB value), WHISPER_LANGUAGE. Backend: new-hook's
  CLIP_TARGET_DURATION and YouTube upload's YOUTUBE_* read env only. DEFAULT_SUBTITLE_STYLE/FONT/SIZE
  were read by nothing; now applied at job creation to fields the request omits (Import form omits them).
- WHISPER_MODEL / WHISPER_LANGUAGE added to DEFAULT_SETTINGS. They were in the settings UI, but saving a value returned 400.
  The Whisper model reloads when the setting changes.
- `GET /api/settings` shows the *effective* value + `source`; UI `saveSettings()` sends only changed fields.
  Job-row copies `subtitle_font/size` are now taken from the normalized style dict (were raw request values).

## Why
Baseline had opposite precedence in the two processes, and most render/analysis settings in the UI
were silently ignored by the worker.

## Decisions & trade-offs
- Defaults: kept what actually ran. `WATERMARK_WIDTH` default = **630** (worker code default), not the
  UI's 480, which never took effect. R-16 revisits it (the old VM's value was 320).
- Values that must agree within a job are read once: `clip_count` per analysis job, preview size
  passed `create_preview` → `render_vertical(size=)`.
- Save-only-changed in the UI: otherwise one Save would copy env/default values into the DB and, with
  DB-wins, freeze them above later `.env` edits.
- DB read failure keeps the last good snapshot and retries after the TTL.
- TIKTOK_* / INSTAGRAM_* left in the whitelist with no consumer (no publisher code exists).
  TELEGRAM_* stay env-only (not in the UI).

## Schema / settings added
Settings: WHISPER_MODEL (base), WHISPER_LANGUAGE (id). No schema change.

## Gotchas for future changes
- Never add `X = os.getenv("X")` module constants for settings; call `setting_int/float()` at use time.
- `ENV_ONLY_KEYS` are never read from the DB (CLIPFLOW_API_KEY etc.).
- An empty DB value = unset. The UI still can't *clear* a DB value (blank fields are skipped); use psql.

## Verification
- Live stack (backend+worker rebuilt): GET shows env-sourced GEMINI_API_KEY as configured/masked.
  PUT GEMINI_MAX_ATTEMPTS=3 over env 4 → backend and worker both 3 (source db). A row changed behind
  the cache was still cached at t+0 and picked up at t+5.2 s. Deleted rows → back to env. A CLIPFLOW_API_KEY row in
  the DB was ignored; PUT of it → 400. PUT WHISPER_MODEL accepted.
- Job create: DEFAULT_SUBTITLE_STYLE=hormozi/SIZE=50 applied when omitted; explicit neon/DejaVu/30 kept.
- Synthetic 1080p testsrc rendered via `render_vertical` (preview 540×960, final 1080×1920); frames
  inspected: crop, watermark, caption correct. pyflakes: no undefined names. Test rows/files deleted.
- NOT verified: a full real job to review (Gemini 503 in R-01), Whisper model hot-reload
  (not triggered), Submagic/YouTube/Runway paths, the settings panel in a browser.
