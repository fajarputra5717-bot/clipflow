# 136 · Clips per video: CLIPS_PER_JOB (per user, default 4, 1–8) + Analyze "Clips: 2 / 4 / 6"; campaign default · settings, main.py, worker.py, campaigns.py, index.html

- **Setting:** `CLIPS_PER_JOB` (user-level key, default 4, PUT validates 1–8) replaces the global `CLIP_COUNT`
  (default 2, never set in the DB on this box). Settings → Clips & rendering "Clips per video (1–8, new jobs)".
- **Snapshot:** `jobs.clip_count` at creation = form choice (`ClipRequest.clip_count`, 1–8) → campaign rules
  `default_clip_count` (new in `GET /api/campaigns`; none set today) → the user's CLIPS_PER_JOB. NULL = legacy job.
- **Worker:** `clips_per_job(job.clip_count)` (else the owner's CLIPS_PER_JOB via run_as_owner), clamped 1–8, read
  once per analysis like before. Hook prompt: only the requested count changes (diffed 4 vs 6: 1 line,
  "N DIFFERENT moments"); overlap rule and every other word unchanged.
- **Analyze:** "Clips 2 / 4 / 6" segmented next to Output platform; pre-selected from the campaign default ("from
  campaign" tag) else your setting ("Your default: N (Settings)"); an explicit pick wins. Payload adds
  `clip_count` (analyze.spec updated: 4 by default).
- Deploy check: the worker image is now import-tested (`docker compose run --rm --no-deps worker python -c "import
  worker"`) before `up`, after 134's crash loop.

**Verified:** harness 85 passed (+ clips: setting default, campaign default tagged, explicit pick wins, payload);
worker image import ok (`clips_per_job`: None→4, 6→6, 99→8); prod: `jobs.clip_count` present, CLIPS_PER_JOB = 4
(default, scope user), CLIP_COUNT gone from the API; prompt diff 4 vs 6 = 1 line.
