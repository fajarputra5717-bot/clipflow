# QA review · cd7e190 · 112 per-clip caption position (edit_spec.caption_y), never below the facecam seam (P1)
Reviewer: Lane C · 2026-10-02 · 30–85 % (else 400); full-frame uses it instead of FULLFRAME_CAPTION_Y; panel clips
`min(override, split)`. Closes 096 Low (captions over in-game HUD) when set per clip. Re-check: gate-P1 (IME 62 %,
Fandra 85 % must stay at the seam). Findings: none.
