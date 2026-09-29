# 008 — Bigger, centered facecam (R-04)
Date: 2026-09-29 · Commit: see `git log --grep R-04` · Files: worker.py, shared/settings.py

## What changed
- `FACE_ZOOM_RATIO` default 0.62 → **0.78** (already read via `setting_float()` since R-02).
- Minimum crop height: flat 180 px → **120 px at 1080p, scaled with source height** (`FACE_CROP_MIN_HEIGHT_1080P`).
- Centering clamp gets a floor (`FACE_CROP_CENTER_FLOOR` = 60% of the requested crop, and never smaller than the
  face itself). Below it the crop keeps the floor size and the edge clamp frames the face off-center; logged as
  "Face crop: centering would shrink crop …".

## Why
The zoom setting did nothing for the case it targets. On the test video (1920x1080, bottom-left webcam, face 111 px),
both 0.62 and 0.78 requested less than 180 px, so the flat minimum decided the crop. Separately, a face tight
against a frame edge could collapse the centered crop to a few pixels (42 px in a synthetic case: 381% "fill", face cut).

## Decisions & trade-offs
- Lower minimum = more upscaling for small webcams (worst case 576/120 = 4.8x vs 3.2x before). Kept a minimum at all
  because a tiny false-positive detection would otherwise zoom into mush.
- Floor also >= face height (added beyond REBUILD's "~60%"): with 60% alone a corner PIP still rendered at 117% fill.
- `max_crop_height = 0.55·H` rechecked: it caps zooming *out* on oversized detections; not what limited zoom.

## Schema / settings added
None new; `FACE_ZOOM_RATIO` default changed. Existing jobs have no stored crop, so their next render uses 0.78.

## Gotchas for future changes
- Zoom changes that seem to do nothing: print `calculate_face_crop()` for the real face box first; the minimum and the
  centering clamp both override the ratio.

## Verification
- Synthetic: centered face 62% → 78% fill; corner/edge faces now <= 100% fill, all crops inside the frame.
- Real job (GiGjvv48z-g, layout=left): preview pane rendered at 0.62 vs 0.78 on the same candidate and inspected:
  face visibly larger at 0.78, horizontally centered. `auto`/`left`/`right` all select the real left-side face
  (selection code unchanged).
- Not verified: a right-side webcam video; a source below 720p.
