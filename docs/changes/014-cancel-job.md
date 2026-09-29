# 014 — Cancel a running job (R-08)
Date: 2026-09-29 · Commit: see `git log --grep R-08` · Files: main.py, worker.py, index.html

## What changed
- `POST /api/jobs/{id}/cancel`: job → `cancelled` (message "Cancelled by user", completed_at), its busy candidates
  (`queued/preview_*/render_*/rendering/thumbnail_*`) → `cancelled`, queued Submagic steps → `failed` ("Cancelled with
  the job"). 404 unknown, 409 if the job isn't running (completed/failed/cancelled/paused/review/partial_failure).
- Worker: `CancelWatch` (daemon thread, DB poll every 2 s) around every analysis job and candidate task; on cancel it
  sets `_cancel_event` and terminates the running subprocess. `run_command` now uses `Popen` so it can be killed.
  Cancellation points: every `StageTimer.start()` (stage boundary), every faster-whisper segment, right after any
  `run_command`. `JobCancelled` is handled before the generic `except Exception` (incl. the per-preview loop).
- `update_job()` / `update_candidate()` never write to a cancelled row, so a stage that was mid-write can't un-cancel it.
- Claims skip cancelled jobs (`claim_candidate_task`, `claim_submagic_task`; analysis claim only takes queued).
- A download cancelled mid-way deletes its `.part` files.
- UI: "Cancel" on running job cards (Import + list) and "Cancel job" in the detail view, `confirm()` first; on success
  the job's poller and candidate watchers stop. `isCancellable()` mirrors the API's list. Badge v2.1108.

## Why
`cancelled` existed in the UI but nothing could set it; a wrong URL meant waiting minutes for download+transcription.

## Decisions & trade-offs
- Real termination, not only between-stage checks: yt-dlp/ffmpeg are killed; in-process Whisper stops at the next segment.
- Submagic work already at Submagic (transcribing/exporting) is not touched: an export may already be billed.
- Candidates in review/completed stay as they are; only in-flight work is cancelled.
- `isBusy()` wasn't reused: its BUSY list lacks `processing`, the status a job spends most time in.

## Verification
- Cancel during download (real job): "Cancel: terminating pid 42", `JOB CANCELLED … [download]`, status stayed
  `cancelled`, no error_stage; the 116 MB `.part` it left prompted the cleanup (verified after the fix: none left).
- Cancel during transcription (real job): 4.2 s from API call to `JOB CANCELLED … [transcription]`; no transcript
  saved; CPU idle afterwards.
- Second cancel → 409. Playwright: Cancel visible on a running card, confirm dialog, status → cancelled, no further
  polls for the job, button gone; no console errors.
- NOT verified: cancel during a candidate preview/final render (same `run_command` kill path as download).
