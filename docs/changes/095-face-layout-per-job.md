# 095 · Facecam layout decided per job, not per clip (P0, QA 087 Medium) · worker.py, main.py

**Before (087).** With layout auto every clip decided alone: one clip's detection miss rendered it full-frame
while its siblings kept the camera panel (or a stray face in a no-cam video gave one clip a junk panel).

**Now.** `decide_face_layout(video, highlights, layout)` runs once per analysis, before the first previews,
and stores `jobs.face_layout = {mode, detected, total, fallback}`:
- strict majority of clips with a face → `panel` for every clip; a clip that missed gets the median box of
  the detected clips (`override: job_panel`, logged);
- strict majority without → `full` for every clip; a stray detection is dropped (`override: job_full`, logged);
- tie → `panel` only if ≥ 2 hits agree in position (within 10 % of the frame of their median), else `full`.
  Measured on this box: in every 1-of-2 job the lone hit was mid-frame (0.21/0.33, 0.60/0.39, 0.30/0.17:
  game or on-screen faces), while the real facecam job hit the same corner box (0.86/0.83) in both clips.
- < 2 clips → NULL (the clip decides, as before). Layout `none` is unchanged (always full).
`detect_face_for_clip(..., face_layout=job["face_layout"])` applies it at all 4 call sites (preview, final,
Submagic clean plate, AI thumbnails); raw detections are cached per process (`_FACE_CACHE`) so the decision
pass doesn't double the detection cost. `face_layout` is threaded through `claim_candidate_task`'s SELECT and
the job dict in `process_candidate_task`.

**Backfill:** all 9 existing jobs with ≥ 2 clips: 4 × panel (2/2), 5 × full (four 1/2 ties without a
consistent facecam, one 0/2).

**Verified** on the stack: panel override on a missing clip (IME 8b974b8e under 1c239a2a's decision →
`detected: True, override: job_panel`, logged); IME job (tie → full) clip 1a9833d4
re-rendered: "detected a face but the job is full-frame (1/2 clips detected); no panel", `face_crop.panel=false`,
frame full-frame like its sibling 8b974b8e.
