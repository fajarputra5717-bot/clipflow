# QA review · eb2c21d · 108 per-clip caption presets + "Apply to all clips"; caption mirror fixed (P1)

Reviewer: Lane C · 2026-10-02

Checked: `clip_candidates.edit_spec` via ensure_schema; PATCH merges (`||`), null removes a key, unknown key/style/
animation → 400 (`shared/edit_spec.py`); worker overlays `edit_spec.caption` on the job style/animation for every
render of that clip (font/size stay job-level, dual-storage rule untouched for the job); `POST /api/jobs/{id}/
caption-preset` updates job style + `subtitle_animation` column, clears clip overrides, re-queues only `review` clips,
records a version per re-queued clip inside the same transaction (version invariant OK); restore carries `edit_spec`
(pre-108 snapshots keep the current spec); preview re-render path still respects `thumbnail_locked`.

## Re-check of the claimed fix (caption mirror): FIXED
`scripts/check_caption_mirror.py` on eb2c21d: "10 styles, 6 animations, 6 presets checked · OK". QA re-introduced the
old drift (hormozi sizeMult 1.4 → 1.35) in a scratch copy → "MISMATCH: hormozi.sizeMult: make_ass 1.4 vs preview
1.35", exit 1. The checker works and can gate CI.

## Findings
1. **Low · "Apply to all" leaves finished clips on the old look** until someone renders a new final (documented, the
   confirm says so). Consider a "needs new final" marker on those clips.
2. **Low · edit/presets specs now force reduced motion** because `html{scroll-behavior:smooth}` plus the taller drawer
   kept Playwright's scroll from settling. Real users get the smooth scroll; worth one manual check that opening a
   drawer doesn't produce a long/janky scroll at 1280 px.

Playwright (git-served 7d26d57, main's suite incl. presets/rules specs + QA capsule): 30 passed, 4 skipped, 0 failed.
Fresh-import render with a per-clip preset: not done here (feature, not a fix) → P1 gate.
