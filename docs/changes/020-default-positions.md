# 020 — New default positions: watermark up, captions down (R-17)
Date: 2026-09-30 · Commit: see `git log --grep R-17` · Files: worker.py, main.py, shared/settings.py, index.html

## What changed
- Settings: `WATERMARK_POSITION_Y` = **25** (centre of the watermark, % of video height from the top) and
  `SUBTITLE_SEAM_GAP` = **1.5** (caption bottom above the facecam seam, % of height). Both in the Settings sheet
  ("Clips & rendering", labelled "new jobs"). Badge v2.1114.
- `jobs.watermark_position_y`, `jobs.subtitle_seam_gap`: `POST /api/jobs` copies the current settings onto the job.
  `job_layout(job)` turns them into fractions; **NULL = legacy layout (50 % / 4 %)**, so jobs created before R-17
  re-render exactly as before, and a later settings change never moves an existing job's layout.
- `make_ass()` takes `watermark_center_y` / `seam_gap_frac`; the gap is floored at 2× the caption outline (the
  outline can't spill across the seam). `get_watermark_rect()` / `render_vertical()` / `apply_watermark_overlay()`
  take the same centre. R-16's collision rule still applies (the watermark moves up if captions reach it).

## Why
TASKS-4-VIDEO T2: watermark and captions shared one band just above the seam; the 4 % gap left ~77 px of dead space.

## Decisions
- 25 % chosen by rendering 20/25/30 at 70:30 (and 25 at 60:40) with hormozi + a 3-line caption: all clear; 25 keeps the
  mark out of the platforms' top UI band without drifting toward the middle. Caption gap 1.5 % = 28 px at 1920.
- No platform safe-zone data exists yet (TASKS-2 T6 not built); revisit when it lands.

## Verification
- Frames (final size): legacy (NULL) reproduces R-16 exactly (watermark 874–1006, caption bottom 1268, gap 76 px);
  25 %: watermark 414–546, caption bottom 1316, seam 1344 (28 px); 60:40 at 25 %: caption bottom 1124, seam 1152.
  Captions above the seam in every variant.
- New job via the API stored `watermark_position_y=25.0`, `subtitle_seam_gap=1.5`.
