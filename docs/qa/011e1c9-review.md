# QA review · 011e1c9 · 099 campaign watermark resolved at job creation; a miss is stored, never a fallback

Reviewer: Lane C · 2026-10-02 · deployed backend + worker confirmed · closes e28421e-review #1 / gate-P0 #1

`jobs.watermark_failure` (ensure_schema); `campaign_watermark_snapshot()` returns `failure` instead of printing
"uses the active watermark"; `POST /api/jobs` returns it in `warnings`; `job_watermark_path()` checks
`watermark_failure` first → False + chip ("…re-create the job"); threaded through the candidate claim, task dict
and Submagic SELECT.

## Re-check: FIXED
- Creation path (backend, read-only call with a fake preset): missing asset → `{'failure': "Campaign watermark
  'QA missing mark' isn't in the watermark library", 'asset_id': None, …}`, log "clips render WITHOUT a
  watermark"; real asset 8f7158d7 → `failure: None`.
- Render path on QA's own test job 4590c193 (asset NULL + failure set) → preview without a watermark
  (`frames/gate-P0/wm-failure-099.jpg`) + `campaign_watermark` chip; restored → chip cleared.

## Findings
- **Low · a later upload doesn't heal the job.** The failure is frozen on the job ("re-create the job"); fine
  for now, but a "retry watermark" action would save re-analysing (AI + transcription cost).
