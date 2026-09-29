# 012 — yt-dlp: `--` before the URL + retry transient download failures
Date: 2026-09-29 · Commit: see `git log --grep "yt-dlp"` · Files: worker.py

## What changed
- `download_video()` passes `--` before the URL (security audit 060: a "URL" starting with `-` was parsed as a
  yt-dlp option, e.g. `--exec=…`).
- Up to 3 attempts (`YTDLP_MAX_ATTEMPTS`), backoff 5 s / 10 s + jitter, only when `is_transient_download_error()`
  matches: HTTP 403/408/429/5xx, timeouts, connection reset/refused, DNS/network errors, IncompleteRead. Private,
  removed, 404 and invalid-URL errors fail on the first attempt. Each retry is logged with the last error line.

## Why
Audit 060 finding; and during R-07 a transient YouTube `HTTP Error 403` on the media URL failed a whole job at the
download stage (a manual retry seconds later worked).

## Decisions & trade-offs
- 403 counts as transient: on YouTube media URLs it is usually a rotating-signature/throttle refusal, not a
  permissions answer. Cost: a genuinely forbidden video takes ~15 s longer to fail.
- Retry wraps the whole yt-dlp run; yt-dlp resumes its own `.part` files.
- Pattern matching on yt-dlp's output text (it exposes no structured error codes on the CLI).

## Verification
- Real yt-dlp: `yt-dlp --simulate -- "--exec=touch /tmp/pwn"` → "not a valid URL", no file created; a real URL
  after `--` still resolves.
- Offline: 8 classifier cases (4 transient, 4 permanent) all correct; fake run_command failing twice with 403 →
  3 attempts then success, `--` is the argument before the URL; permanent error → 1 attempt.
- NOT verified: a real transient failure recovering in production (can't provoke YouTube's 403 on demand).
