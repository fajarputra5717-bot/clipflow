# 010 — Submagic gets a clean plate (R-06)
Date: 2026-09-29 · Commit: see `git log --grep R-06` · Files: worker.py

## What changed
- `render_vertical()`: `subtitle_path=None` skips the subtitles filter, `watermark=False` skips the overlay and its
  `-loop 1 -i watermark` input. Stages chain through `last`; the graph always ends in `[{last}]null[video]`.
- `render_clean_plate(candidate, job, video_path)`: 1080x1920 stacked render with no subs and no watermark, cached as
  `PREVIEW_DIR/<candidate_id>_clean.mp4` (written to a temp name, then renamed).
- Submagic `uploading` uploads the clean plate instead of `preview_path` (claim SELECT adds `j.split_ratio, j.layout`).
- `create_preview()` deletes the cached clean plate, so a new hook / any re-rendered edit can't upload stale footage.

## Why
The preview has our ASS captions burned in; Submagic added its own on top, so the output had two caption tracks.

## Decisions & trade-offs
- Reused `render_vertical()` with flags instead of copying the still-frame helper's filter graph (TASKS suggested
  reusing that shape; one render path is less duplication than either). R-09 uses the same `subtitle_path=None` path.
- Clean plate at final size and final x264 settings (Submagic re-encodes; start from the best copy).
- Upload no longer needs a preview to exist, only the source video.

## Gotchas for future changes
- New optional filter stage in render_vertical → end it with `;`, name its output, set `last`. Never write `[video]`
  directly; the trailing `null` does that.
- Anything that changes a candidate's times/crop must go through create_preview (or delete `_clean.mp4` itself).

## Verification
- `render_clean_plate` on a real candidate: 6.1 s, h264 1080x1920 yuv420p + aac, 35.0 s; frame inspected: no
  watermark, no captions. Second call served from cache (0.0 s).
- Regression: preview re-render still produces watermark + neon captions (frame inspected); the filter chain logged
  `stacked → watermarked → subtitled → video`; the cached clean plate was deleted.
- NOT verified: an actual Submagic upload (creates a project in the user's Submagic account; not triggered) and so
  the "exactly one caption track" acceptance on Submagic's output.
