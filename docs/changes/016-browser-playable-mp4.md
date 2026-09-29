# 016 — Preview/final video plays in the browser (R-10)
Date: 2026-09-29 · Commit: see `git log --grep R-10` · Files: worker.py

## What changed
- Both browser-facing encoders (`render_vertical()`: preview, final, clean plate; `apply_watermark_overlay()`:
  Submagic final) now pass `-profile:v high`; the overlay re-encodes audio to AAC 128k instead of `-c:a copy`.
  Already present and kept: libx264, `-pix_fmt yuv420p`, AAC, `-movflags +faststart`. `BROWSER_MP4_NOTE` in worker.py.

## Why
REBUILD R-10: a native preview once failed to play in the browser. The profile wasn't pinned and the Submagic overlay
passed through whatever audio codec Submagic returned.

## Decisions & trade-offs
- `-profile:v high` is an upper bound in x264: previews (`ultrafast`) come out **Constrained Baseline** (no High-only
  tools used), a subset every browser decodes. Finals are High. Not forced further.
- No nginx change needed: the file routes already answer Range with 206 through nginx.

## Verification
- ffprobe: final `h264 High 1080x1920 yuv420p` + `aac LC`; preview `h264 Constrained Baseline 540x960 yuv420p` + `aac LC`.
  Both: top-level boxes `ftyp moov free mdat` (moov before mdat).
- Range through nginx with `?mt=`: `bytes=0-1023` → 206 `content-range: bytes 0-1023/<size>`, mid-file range → 206,
  `accept-ranges: bytes`, `video/mp4`; without token → 401.
- Playback, the real in-app `<video>` in the candidate card: **Chromium 153** (Playwright, reports H.264 support)
  and **WebKit 26.6** (Safari's engine; Playwright's official Docker image, so nothing installed on the host) both play
  the 1080x1920 render (currentTime +2.4–2.5 s in 2.5 s), no errors. Seek to 20 s works.
- NOT verified: real Safari on macOS/iOS (WebKit on Linux uses GStreamer, not AVFoundation).

## Gotchas for future changes (test harness)
- Headless WebKit does not advance a `<video>` that isn't rendered (appended off-flow/hidden): make it visible.
- Several `<video>` elements alive on one WebKit page starve its GStreamer decoders: one page per clip.
  Both produced false "won't play" results here before being ruled out with reference clips.
