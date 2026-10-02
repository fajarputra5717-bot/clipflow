# 087 · No-facecam layout: full-frame gameplay instead of a junk bottom panel (QA #6) · worker.py, main.py, index.html

**Before.** With no face detected the render still stacked a "facecam" panel cropped from a guessed
bottom-right box (QA clips #4: 8b974b8e showed a zoomed slice of jacket/floor in the bottom 30 %).

**Now.**
- `jobs.layout` accepts `none` (Import → Facecam → "No facecam"); `detect_face_for_clip(layout="none")`
  skips detection and returns `detected: False`.
- `calculate_face_crop()` adds `panel` (= a face was detected and layout ≠ none) to `face_crop`.
- `vertical_layout_filter(width, height, split_ratio, face_crop)` is the one layout graph, used by
  `render_vertical()` (preview, final, Submagic clean plate) and `extract_thumbnail_base_frame()` (AI
  thumbnails): `panel` false → the gameplay is scaled/cropped to fill the whole 9:16 frame. Captions and the
  watermark keep their split-ratio positions (clear of the platform's bottom UI band). Log lines:
  "No face detected: full-frame crop, no facecam panel", "Render: no facecam panel, full-frame gameplay crop".
- Import picker: 4 choices (`.facecam-grid`); summary shows "No facecam".

**Not changed.** ccc2a5b1's duplicate camera is a different cause: a face *was* detected and the stream's
own cam overlay sits inside the centre gameplay crop. Possible fix (not done): shift the gameplay crop
window horizontally so it excludes the detected cam box when the source is wide enough.

**Verified** on the stack: final of 8b974b8e (auto, no face) re-rendered full-frame (`face_crop.panel=false`,
frame checked; karaoke + watermark + −14.3 LUFS intact); layout `none` and a face-detected source
(ccc2a5b1) through the shared graph → full frame vs. panel; `POST /api/jobs` accepts `layout: none`;
Import picker at 1280/390 px.
