# 021 — ffmpeg render watchdog
Date: 2026-09-30 · Commit: see `git log --grep watchdog` · Files: worker.py, CLAUDE.md

## What changed
- `run_command(..., timeout=)`: on expiry the process is killed and `RenderTimeout` (a `TimeoutError`) is raised.
- `render_vertical()` (preview, final, clean plate) and `apply_watermark_overlay()` pass
  `render_timeout_seconds(duration)` = max(300 s, 10 × clip duration); the overlay reads the duration from the file.
- `failure_class()` already treats `TimeoutError` as transient, so R-15 requeues the task with backoff until
  `JOB_MAX_ATTEMPTS`.

## Why
R-15's heartbeat thread keeps a claim alive while ffmpeg hangs (stuck decoder, stalled disk), so a hung render
blocked the single worker indefinitely.

## Decisions & trade-offs
- Only renders are watched. Download (yt-dlp has its own socket timeouts) and AV1 normalization (full-length
  re-encode, duration unknown up front) are not.
- 10× is generous: a 35 s final takes ~10 s here, so the 350 s limit only fires on a real hang.

## Verification
- Forced (limits patched to 1 s in a one-off process) on a real 20 s final render: killed after 1.1 s, no ffmpeg left
  running; `record_failure()` on a fixture candidate → `render_queued`, transient, attempt 2/3, retry_after set.
- Normal limits: 350 s for a 35 s clip, 600 s for 60 s.
