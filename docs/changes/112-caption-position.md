# 112 · Per-clip caption position (P1; fixes captions over in-game HUD, QA 096 Low) · worker.py, shared/edit_spec.py, index.html

`edit_spec.caption_y` = caption anchor, % of height from the top (30–85; missing = auto = today's placement).
`caption_split_ratio(split, face_crop, override)`: full-frame clips use it instead of `FULLFRAME_CAPTION_Y`;
camera-panel clips can only move UP from the seam (`min(override, split)`), never into the facecam. Both
make_ass calls (preview, final) pass the clip's value. UI (Captions tab): "Caption position" with a "Custom for
this clip" checkbox + 30–85 % slider (Auto when unchecked); Apply sends the number, or null for Auto, only when
changed. Test in `keywords.spec.js`.

**Verified:** PATCH 20 → 400; IME full-frame clip 1a9833d4 at 62 → MarginV 382/960, caption bottom 60 % (auto
was 76 %); reset to auto and re-rendered; harness 32/32.
