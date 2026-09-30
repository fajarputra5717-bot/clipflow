# 018 — Failure recovery: heartbeat, stale-claim reclaim, retries (R-15)
Date: 2026-09-30 · Commit: see `git log --grep R-15` · Files: worker.py, main.py, shared/errors.py, shared/settings.py, index.html

## What changed
- Schema (jobs + clip_candidates): `heartbeat_at`, `attempts` (failures so far), `error_class`
  (`transient|permanent`), `retry_after`. Settings: `JOB_MAX_ATTEMPTS` (3), `STALE_CLAIM_MINUTES` (5).
- Heartbeat: the R-08 `CancelWatch` thread writes `heartbeat_at` every 30 s while a job/candidate task runs; claims
  set it on claim.
- `reclaim_stale()` replaces `reset_orphans()` (which failed everything in flight on restart). At startup every
  `processing` job / `*_rendering` candidate is orphaned; afterwards (idle, every 60 s) those whose heartbeat is older
  than `STALE_CLAIM_MINUTES`. Requeued with attempts+1 (job → `reanalyze_queued` if a transcript is stored, else
  `queued`; candidate → its queue) or `failed` at `JOB_MAX_ATTEMPTS`. Candidates of jobs being re-analysed are skipped.
- `shared/errors.failure_class(exc)`: typed AI errors decide themselves; otherwise yt-dlp/network/429/5xx/OOM
  patterns → transient, removed/private video, invalid/unsupported media, disk reserve, retention purge → permanent;
  unknown → permanent (no endless loops). `record_failure()` requeues transient failures with backoff
  (60 s × 2^(n-1), max 1 h) via `retry_after`, which both claims respect, until `JOB_MAX_ATTEMPTS`; otherwise `failed`
  with a plain message ("Failed, needs attention: …" / "Failed after N attempts (temporary problem kept recurring)").
  Success resets attempts/error_class.
- `POST /api/jobs/{id}/retry` (failed only; reanalyze if transcript + unpurged source, else from scratch) and
  `POST /api/jobs/{id}/candidates/{cid}/retry` (failed only; back to the queue it failed in; 409 if the job is
  cancelled). Both reset attempts; edits and version history untouched.
- UI: Retry on failed job cards and "Retry job" in the detail view; failed candidates show a banner with the reason
  (amber = temporary, red = needs attention) and Retry. Badge v2.1112.

## Decisions & trade-offs
- Dedicated `heartbeat_at`, not `updated_at`: retention age and the Submagic poll throttle already use updated_at.
- The heartbeat thread proves the process is alive, not that ffmpeg is progressing; a hung ffmpeg is not reclaimed.
- Submagic `uploading`/`applying` are not heartbeated/reclaimed yet (their claim isn't wrapped in CancelWatch).

## Verification
- Real crash: worker restarted 45 s into transcription (heartbeat was fresh) → startup `Reclaimed job … -> queued
  (attempt 1)` → re-claimed at once, download reused, reached review with attempts reset to 0.
- Fixtures: stale heartbeat → requeued; 10 s old heartbeat → untouched; 3rd crash → failed "stopped … 3 times";
  AI 503 → `reanalyze_queued`, transient, retry_after set, "retrying in 1 min (attempt 2/3)"; claim skips it while
  retry_after is in the future and takes it once passed; "Video unavailable" → failed/permanent at once.
- UI (Playwright): failed candidate banner + Retry → `render_queued` → final rendered (completed); failed job card
  Retry → `reanalyze_queued`, attempts 0; retrying a non-failed job → 409. No console errors besides that probe's 409.
- Found (baseline): re-analysis deletes old candidate rows but not their files; the orphan sweep (R-14) catches them.
