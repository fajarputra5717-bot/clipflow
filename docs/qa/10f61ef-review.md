# QA review · 10f61ef · 096 full-frame captions at FULLFRAME_CAPTION_Y (P0, QA 087 Low)

Reviewer: Lane C · 2026-10-02

`caption_split_ratio()` → seam when there's a panel, else `FULLFRAME_CAPTION_Y` (default 78, clamped 60–85); used
for both make_ass call sites (preview, final). New setting only in `DEFAULT_SETTINGS` (read at use time, OK).

## Findings
1. **Low · right-hand icon column.** At 78 % long two-line captions span x ≈ 10–90 %; TikTok/Reels put the
   like/comment column at x ≥ 83.9 % between ~50–85 % height (MotionKlip guide), so line ends can sit under it.
   Not a blocker; worth a max caption width of ~80 % in full-frame mode.

## Re-check
Frames in gate-P0.md (IME/GTA full-frame clips).
