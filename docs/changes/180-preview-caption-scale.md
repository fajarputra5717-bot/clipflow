# 180 · Preview captions scale every metric with the preview size (Lane C Medium, 2026-10-09)

- Bug: 540 px previews got half the font size (create_preview) but the 1080 outline, shadow and 40 px side margins,
  so preview captions looked ~2× bolder than the final (outline 9 px at 540 wide vs 9 px at 1080).
- `make_ass()` now scales outline, shadow and MarginL/R by `canvas_width / FINAL_WIDTH` (side margin =
  `CAPTION_SIDE_MARGIN_1080`); the seam gap and caption-block estimate follow because they use the outline. Animation
  tags are percentages/colours only (nothing to scale). Finals at 1080 are unchanged (factor 1.0).
- Verified: the same caption rendered at 540 (upscaled) next to 1080, Heavy Outline + Hormozi, before/after:
  docs/ui-recordings/caption-scale-180/ (gitignored). Preview ASS now `…,1,4.5,0.5,2,20,20,…` vs final `…,9,1,2,40,40,…`.
  check_caption_mirror OK. Deployed worker + sender (idle, import-tested).
