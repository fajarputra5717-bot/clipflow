# 019 — One watermark geometry + caption collision fix (R-16)
Date: 2026-09-30 · Commit: see `git log --grep R-16` · Files: worker.py, shared/settings.py, index.html

## What changed
- `get_watermark_rect(canvas_w, canvas_h, watermark_width, watermark_path)` is the single source of the watermark's
  x/y/w/h. It uses the PNG's **alpha bounding box** (`watermark_alpha_bbox`, cached per path+mtime): the asset is
  cropped to the visible mark, which is scaled to `watermark_width` (now = visible width on a 1080-wide video), centred.
- `watermark_filter(rect, …)` builds the ffmpeg chain (`crop,scale,…,overlay=x:y`) for `render_vertical()` and
  `apply_watermark_overlay()`; `make_ass()` returns the rect it cleared the captions against and the render uses
  exactly that rect (create_preview/render_final resolve the asset path once and pass it to both).
- Collision check on the caption's **top** edge: `H − margin_v − (effective_size × 3 lines × 1.2 + 2 × outline)`.
  On overlap (with a 1.5 % gap) the **watermark moves up**, floored at the 4 % top margin; logged. The seam margin is
  a floor: the old `margin_v = min(seam, watermark-safe)` clamp, which could push captions below the seam into the
  facecam, is gone. `_watermark_pixel_size()` removed.
- `WATERMARK_WIDTH` default 630 → **320** (REBUILD: the old VM's value; 630 scaled the whole canvas PNG). Badge v2.1113.

## Why
The active asset is a 1080×1920 transparent canvas with a 394×163 mark near its bottom. Scaling the canvas and centring
it put the mark at y≈1247–1341, on the 70:30 seam, in the caption band; make_ass measured the caption's bottom edge and
the full PNG, so its clamp never fired where it mattered.

## Decisions & trade-offs
- Line estimate: constant 3 (conservative, deterministic; ASS wraps by width, which make_ass doesn't measure). Cost:
  with short captions the watermark may move up a bit more than strictly needed.
- Resolution order: captions keep their seam-anchored position (never lower into the facecam), the watermark yields.
- Submagic output: same geometry, no caption clearance (its captions can't be measured).
- Position is still the vertical centre here; R-17 makes it a setting.

## Verification (final 1080×1920, hormozi, Montserrat Black 42 → 59 px, 3-line caption, real make_ass + render_vertical)
- 70:30: caption top 1035, watermark moved 894 → 874 (logged); frame: caption above the seam, mark clear above it.
- 60:40: caption top 843, watermark moved 894 → 682 (logged); frame: caption above the seam (y 1152), mark clear.
- No-subtitle render and `apply_watermark_overlay()` produce valid h264/aac output with the same rect; preview canvas
  rect scales to 160×66.
- NOT verified: the fallback baked-in `assets/watermark.png` (tight 640×140 PNG, bbox 344×76) in a frame.
