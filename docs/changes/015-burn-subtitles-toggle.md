# 015 — Optional burn-in: subtitle-free output (R-09)
Date: 2026-09-29 · Commit: see `git log --grep R-09` · Files: main.py, worker.py, index.html

## What changed
- `jobs.burn_subtitles BOOLEAN DEFAULT TRUE` (existing jobs = TRUE; NULL also means on, `job_burn_subtitles()`).
- Worker: when off, `create_preview()` / `render_final_candidate()` set `subtitle_file = None`, skip `make_ass()`
  entirely (no .ass written) and call `render_vertical(subtitle_path=None)`. Threaded via `claim_candidate_task`'s
  SELECT + the job dict; analysis-time previews get it from `j.*`.
- `PATCH /api/jobs/{id}/render-options` accepts `burn_subtitles` (with R-05's watermark fields); returned by the job GETs.
- Edit panel: "Burn subtitles into video" checkbox under the subtitle text, checked by default, sent by
  `applyEdits()` only when changed; the preview note says when subtitles are off. Badge v2.1109.

## Decisions & trade-offs
- Same render path as R-06's clean plate (`render_vertical`'s optional subtitle stage), not a third composition:
  the clean plate also drops the watermark, burn-off keeps it, so the two outputs differ but share one code path.
- Job-level, like subtitle style and watermark: it applies to every candidate of the job on their next render.
- Subtitle text, override and style/font/size/animation are never touched by the toggle.
- Submagic is unaffected (it always gets the clean plate).

## Verification (candidate 59d0…, job style Anton / neon / bounce)
- UI uncheck + Apply → PATCH `{"burn_subtitles":false}` → preview re-rendered; frame at 6 s has no caption (it had
  "TIDAK APA?"), watermark present; the preview .ass was not rewritten. Final render: no caption, no `_final.ass`.
- DB after: font Anton, style neon, animation bounce, subtitle_override unchanged.
- UI re-check + Apply → PATCH `{"burn_subtitles":true}` → preview .ass `Style: Default,Anton,28,0`, frame shows
  "TIDAK APA?" in Anton neon again. No console errors.
- NOT verified: a final render after re-enabling (same code path as the preview); that test candidate's current
  final render is the caption-free one.
