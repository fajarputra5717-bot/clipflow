# QA review · e28421e · 092 campaign watermark missing → no watermark + failing chip (P0)

Reviewer: Lane C · 2026-10-02 · deployed worker confirmed

Code checked: `job_watermark_path()` (job asset → path, missing → `False` + "campaign_watermark" chip + WARNING
log; found → chip cleared; no asset → active watermark as before) · `False` handled everywhere: `make_ass` skips
geometry (`ValueError` inside its try), `render_vertical(watermark_path=False)` renders without a mark,
Submagic apply moves the raw file instead of overlaying · wired into create_preview, render_final_candidate and
the Submagic apply step.

## Re-check (fresh import, campaign ime-roleplay, job 4590c193)
Asset 8f7158d7 snapshotted on the job; both previews and the final of af550230 carry the "instgrm :
@motion.klip" mark at ≈ 25 % (`frames/recheck-092/final-af550230.jpg`); no render warnings. Happy path PASS.

## Findings (most severe first)
1. **Medium · the silent fallback still exists at JOB CREATION.** `campaign_watermark_snapshot()`
   (`backend/app/main.py`, unchanged) stores `watermark_asset_id = NULL` when the campaign's asset isn't in the
   library ("the job uses the active watermark"). The worker then sees a job without an asset and uses the active
   watermark: no chip, no warning. 092 only covers an asset that disappears after creation. Fix: when a campaign
   requires a watermark and the asset can't be resolved, store the preset id anyway (so the worker fails it with
   the chip) or refuse the job with a 400.

## Not verified
- The missing-asset path live (would need deleting a library asset or a rules file pointing at a missing id;
  QA doesn't touch either). Code-read only.
