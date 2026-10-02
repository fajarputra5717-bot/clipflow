# QA review · c72a70a · 079 per-job language (Auto/English/Indonesian)

Reviewer: Lane C · 2026-10-02 · reviewed against committed HEAD (not Lane A's working tree)

Invariants checked: ensure_schema (5 `ADD COLUMN IF NOT EXISTS`, OK) · claim SELECT `j.*` carries
`language`/`language_fallback` into `_process_analysis_job` (OK) · reanalyze path reads stored
`effective_language` (OK) · Submagic claim SELECT threads `language`/`effective_language` (OK) ·
Indonesian hook-prompt text byte-identical when language=id/legacy (OK, `build_hooks_prompt`) ·
frontend: delegated `[data-language]` click + keydown, localStorage wrapped in try (OK) ·
faster-whisper 1.2.1 in the container supports `language_detection_segments` (verified).

## Findings (most severe first)

1. **Medium · behaviour change for API callers.** `ClipRequest.language` defaults to `"auto"`
   (`backend/app/main.py:441`), not NULL. A `POST /api/jobs` without `language` (scripts, future
   Telegram/automation) now auto-detects with no fallback → `languages.DEFAULT` instead of the old
   `WHISPER_LANGUAGE` path. The change doc says "NULL = legacy", but nothing new can ever produce NULL.
   Today only index.html creates jobs (grep), so impact is latent.
2. **Low · `WHISPER_LANGUAGE` setting is now dead for new jobs** but still shown in Settings as
   "Transcription language" (`index.html:2738`). Only pre-079 rows (language NULL) read it
   (`worker/worker.py:1637`). Users changing it will see no effect.
3. **Low · Auto with no explicit history defaults to Indonesian.** `language_fallback` is NULL
   until the user has once clicked English/Indonesian (localStorage, per browser). A low-confidence
   English video from a fresh browser → transcribed as `id`. Documented as intended; flag for UX.
4. **Process · version badge not bumped** for a user-visible change (badge still v2.1116; REBUILD
   ground rule). Change 079 was also committed before 078 (INDEX order 078, 079; git order reversed).

## Not verified
- No end-to-end Auto job was run (queue rule: one job, only when idle; deferred to a later QA slot).
  Detection confidence behaviour, fallback logging and `effective_language` write are code-read only.
- English prompt quality of `fix_subtitle_ai` / `generate_description` / `new_hook` titles.
- `language_detection_segments=3` cost on long videos (detection + possible second decode pass).
