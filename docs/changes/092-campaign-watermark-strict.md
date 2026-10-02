# 092 · Campaign watermark: no silent fallback (P0, QA 081 #2) · worker.py

**Before.** `resolve_watermark_path(asset_id)` logged "not found; using the active one" and burned whatever
watermark was active: a campaign clip could ship with another brand's mark and nobody would see it.

**Now.** `job_watermark_path(job, candidate_id)` is the resolver for every render of a job (preview, final,
Submagic apply). A job with its own asset (`jobs.watermark_asset_id`, the 081 campaign snapshot):
- asset resolved → that file; any old `campaign_watermark` warning is cleared;
- asset missing → **no watermark at all** (never a fallback), a `WARNING: campaign watermark asset … not found
  (campaign …); rendering WITHOUT a watermark` log line, and a failing `campaign_watermark` render warning
  ("Campaign watermark missing … Upload it, then re-render.") shown as a chip (091). P1's rule chips / approve
  gate will read it.
Jobs without an asset keep using the active watermark. `False` = "no watermark" through `make_ass()`
(no caption clearance) and `render_vertical()` (no overlay); Submagic apply moves the raw file instead of
overlaying.

**Verified** on the stack: Windah test job pointed at a missing asset id → preview has no watermark (frame),
WARNING logged, chip set; real asset restored → watermark back, chip cleared.
