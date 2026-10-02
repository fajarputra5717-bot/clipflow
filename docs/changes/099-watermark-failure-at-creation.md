# 099 · Campaign watermark resolved at job creation; a miss is stored, never a fallback (pre-P1 #1, QA Medium) · main.py, worker.py, index.html

**Before.** 092 made render-time resolution strict, but `campaign_watermark_snapshot()` at job creation stored
`watermark_asset_id = NULL` when the campaign's asset wasn't in the library, so the worker saw "no campaign
asset" and silently burned the active watermark: no chip.

**Now.**
- `campaign_watermark_snapshot()` returns `failure` (asset not in the library by id or name, or the lookup
  errored); `POST /api/jobs` stores it in the new `jobs.watermark_failure` column and returns it in
  `warnings` (the Import form shows it as an 8 s toast).
- `job_watermark_path()` checks `watermark_failure` first: render WITHOUT a watermark, WARNING log, failing
  `campaign_watermark` chip ("… isn't in the watermark library. Upload it …, then re-create the job.").
  Threaded through `claim_candidate_task`, the Submagic claim and the candidate job dict; the analysis job
  claims `j.*`.
- So no path falls back silently: creation-time miss (099) and render-time miss (092) both end in
  no watermark + chip.

**Verified:** snapshot with a bogus asset id/name → `failure` set, real campaign → asset id, no failure;
Windah test job with `watermark_failure` set → preview has no watermark (frame), WARNING logged, chip text
as above; failure cleared → watermark back, chip cleared.
