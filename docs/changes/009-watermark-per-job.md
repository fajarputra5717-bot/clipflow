# 009 — Per-job watermark size/opacity (R-05)
Date: 2026-09-29 · Commit: see `git log --grep R-05` · Files: main.py, worker.py, index.html, CLAUDE.md

## What changed
- `jobs.watermark_width INT`, `jobs.watermark_opacity REAL` (NULL = global `WATERMARK_WIDTH`/`WATERMARK_OPACITY`).
- `PATCH /api/jobs/{id}/render-options`: writes only the fields present in the body; explicit null resets.
  Width 100–1080, opacity 0–1 (422 otherwise). Returned by `GET /api/jobs[/{id}]`.
- Worker: `job_watermark(job)` resolves (width, opacity) once per render and passes it to both `make_ass()` (caption
  margin under the watermark) and `render_vertical()`; threaded via `claim_candidate_task` SELECT + the job dict.
- Submagic `applying`: download to `_submagic_raw.mp4`, then `apply_watermark_overlay()` (same centered geometry,
  x264 yuv420p faststart, audio copied) → `_submagic.mp4`.
- Edit panel: section 4 "Watermark" (size 200–900 px slider, opacity slider, relative-size bar); `applyEdits()` sends
  only moved controls, so an untouched job stays NULL. Badge v2.1102.

## Also fixed (pre-existing, found while testing; both break R-09's acceptance)
- Edit panel read `c.subtitle_font/...` from the candidate row, which never has them, so it always showed defaults and
  **Apply reset the job's style**. `renderCandidate()` now gets the job and reads the style from it.
- Backend `normalize_subtitle_style()` treated the dropdown's preset string ("neon") as a font name, so the
  **Font style dropdown never changed anything**. Preset names (`SUBTITLE_STYLE_PRESETS`) now set `style`.

## Decisions & trade-offs
- One job-level endpoint instead of widening subtitle-style: R-09 adds `burn_subtitles` to the same endpoint.
- Watermark is job-level (like subtitle style): changing it on one candidate affects the job's other candidates on their next render.
- Overlay after Submagic reads the video width with OpenCV to scale the mark; no scale2ref (version-dependent).

## Gotchas for future changes
- New render path → call `job_watermark(job)` once and pass the same values to make_ass + render_vertical.
- Adding a subtitle preset → `styles` in make_ass, `SUBTITLE_STYLE_PRESETS` in main.py, `SUBTITLE_STYLES` in index.html.

## Verification
- API: 200 on set/reset, 422 on width 50, 404 on unknown job, empty body = no-op.
- Real preview renders: 400 px / 0.5 → overlay `scale=200` (540 preview) `aa=0.5`, visibly smaller and translucent;
  reset → 315 / 1.0. Frames inspected.
- `apply_watermark_overlay()` on an existing vertical mp4 (stand-in for a Submagic download): h264 yuv420p + aac, mark
  centered at the requested size.
- Playwright (Chromium): panel shows job style neon/56/bounce; sliders update labels/bar; Apply PATCHes
  render-options `{"watermark_width":450,"watermark_opacity":0.6}`; DB matches.
- NOT verified: a real Submagic apply (export is billable; not triggered).
