# QA review · fd96c63 · 087 no-facecam layout (claims QA clips #4 / summary #6)

Reviewer: Lane C · 2026-10-02 · deployed backend + worker confirmed to contain it

Invariants checked: layout threading unchanged (same 3 call sites; `none` handled in
`detect_face_for_clip`) · one layout graph `vertical_layout_filter()` used by `render_vertical()` (preview,
final, clean plate) and `extract_thumbnail_base_frame()` (AI thumbnails) · `create_preview()` and
`render_final_candidate()` both re-detect + `calculate_face_crop()` on every render, so old candidates pick up
`panel` on their next render; stored `face_crop` rows without `panel` default to the split (legacy-safe) ·
`SUPPORTED_LAYOUTS` + error text updated; frontend picker uses the delegated `[data-layout]` handler ·
`thumbnail_locked` / watermark resolver untouched.

## Findings (most severe first)
1. **Medium · auto layout flips per clip on detector misses.** With `auto`, `panel` = "a face was
   detected in this clip". A facecam stream where detection misses one clip (face turned away, dark scene)
   now renders that clip full-frame while its siblings have the cam panel: a silent per-clip layout
   change. Previously it fell back to a corner crop (often still the cam). Consider a job-level decision
   (majority of clips) or a confidence floor before dropping the panel.
2. **Low · full-frame crop shows ~32 % of a 16:9 frame's width** (centre crop to 9:16). Expected for this
   layout; on HUD-heavy games side elements are lost. No pan/scan.
3. **Low · no badge bump** for the new Import choice (still v2.1116).
4. **Known, not changed:** ccc2a5b1's duplicate camera (different cause, see the change doc).

## Re-check: FIXED (fresh-import e2e, QA job f20ba7e7, 2026-10-02 10:38–10:45)
New job on https://www.youtube.com/watch?v=bRJnLhJruyc (GTA RP, no streamer cam), layout `auto`, language
`id`, no campaign; worker with 087 + 088 + 089 deployed. Path: new job → transcription → first preview → final.
- Both candidates: `face_crop.panel = false`, logs "No face detected: full-frame crop, no facecam panel" /
  "Render: no facecam panel, full-frame gameplay crop".
- **First preview** 0b69c38a (540×960): full-frame gameplay at 0 / 25 / 50 % / end, no bottom panel;
  watermark ≈ 25 %; karaoke sweeps word by word (`frames/e2e-087-f20ba7e7/preview-*`).
- **Final** (1080×1920, 34.0 s): same layout; karaoke sweep ("ITU" → "GAK ADA I…" → "…DAMAS"); loudness
  **−14.1 LUFS, LRA 7.0, true peak −1.1 dBTP** (worker log: −27.1 → −14.1). `frames/e2e-087-f20ba7e7/final-*`.
- Low · in full-frame mode captions stay at the split-seam height (≈ 67 %), which on this source sits on the
  game's own HUD panel (respawn box); legible, but overlaps in-game UI.
- Note · true peak −1.1 dBTP passes the −1 ceiling with 0.1 dB margin (the 0.5 dB codec headroom is
  mostly used by AAC on this clip).

## Not verified
- Layout `none` end to end (QA's e2e used `auto`, the fallback path that caused QA #6).
- Candidate 9c5f3050's final (only its preview, panel=false, was produced).
