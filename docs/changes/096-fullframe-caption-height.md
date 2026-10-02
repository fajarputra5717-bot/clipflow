# 096 · Full-frame clips: captions lower (P0, QA 087 Low) · worker.py, shared/settings.py, index.html

**Before.** Full-frame (no facecam panel) clips kept the captions at the old seam height (bottom ≈ 67 %),
high in the frame with nothing below them.

**Now.** `caption_split_ratio(split_ratio, face_crop)` is the anchor passed to `make_ass()` by preview and
final: the seam with a panel, otherwise the new runtime setting `FULLFRAME_CAPTION_Y` (default 78 % from the
top, clamped 60–85 so the caption block stays above the platforms' bottom UI band ≈ 87 %). The caption bottom
sits the seam gap above the anchor. Settings sheet → "Clips & rendering" → "Caption height, no-facecam clips".

**Verified:** IME clip 1a9833d4 (job full-frame) re-rendered: MarginV 229 / 960 → caption bottom at 76.1 %
(was ≈ 67 %); frame shows the caption at ≈ 75 %, watermark unchanged; `GET /api/settings` reports 78 (default).
