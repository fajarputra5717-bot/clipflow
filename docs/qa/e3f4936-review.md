# QA review · e3f4936 · 117 campaign default facecam layout (IME = no facecam) (P2 carry-in, gate-P1 #1)

Reviewer: Lane C · 2026-10-05 · deployed backend confirmed

`ClipRequest.layout` now optional; omitted → `campaigns.default_layout(rules)` (rules key `default_layout`, unknown →
"auto"), else "auto". Rules: IME `none`, Fandra and MotionKlip `auto`. UI pre-selects the campaign default until the
user picks a layout (`layoutTouched`). New Playwright spec `campaign-layout.spec.js`.

## Re-check: FIXED (fresh import)
`POST /api/jobs` for ime-roleplay with NO layout → job 31dc06f4 stored `layout = none`, `face_layout` NULL (detection
skipped), both first previews `panel=false`, clean full-frame (`frames/recheck-117/`). Fandra default `auto` code-read.

## Findings
- None. Note: the face-detection fix itself (the other half of gate-P1 #1) is still pending (118).
