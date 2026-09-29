# 063 — YouTube URL allowlist + strict upload re-encode (audit-001 F4/F5)
Date: 2026-09-29 · Commit: see `git log --grep "audit-001 F4"` · Files: backend/app/main.py, docs/security/audit-001.md

## What changed
- `validate_youtube_url()` (main.py, next to `SUPPORTED_LAYOUTS`) runs in `create_job`. It allows `https` only, on
  hosts `YOUTUBE_URL_HOSTS` = youtube.com / www / m / music.youtube.com / youtu.be. It rejects userinfo, ports
  other than 443, whitespace and control characters, and a leading `-`. Failure → 400 `youtube_url must be an https://
  link on …`. The stripped URL is what gets stored.
- `reencode_uploaded_image(raw, fmt)` is shared by the thumbnail and watermark uploads. It runs Pillow `open` +
  `verify` + a fresh decode, caps at `UPLOAD_MAX_PIXELS` = 40 MP (explicit check + `Image.MAX_IMAGE_PIXELS`, with
  the bomb warning raised as an error), then re-encodes (JPEG q92 / RGBA PNG). Any failure → 400. The
  raw-bytes fallback is gone. The thumbnail upload now validates before its DB lookup.

## Why
audit-001 F4 (yt-dlp option injection + SSRF) and F5 (raw bytes saved when Pillow fails, including bombs).

## Decisions & trade-offs
- The allowlist is exact hosts, not a `*.youtube.com` suffix match. Anything else is rejected rather than rewritten.
- 40 MP is about 5× a 4K frame, far above any real thumbnail or watermark.
- Pillow's decoder serves as the magic-byte check. The client `Content-Type` check stays as a cheap first filter.

## Gotchas for future changes
- **worker.py still needs `--` before the URL in the yt-dlp argv** (defence in depth; Lane A).
- Jobs created before this change aren't re-validated.
- The frontend shows the 400 detail as is, so keep the message user-readable.

## Verification
Ran in a throwaway `riftstorm-backend` image container (`--network none`, this main.py mounted, no DB) through the
FastAPI TestClient, with the real auth middleware. 6 valid URLs pass validation (then fail on the missing DB, as
expected). 15 hostile ones → 400. Uploads: SVG-as-png, HTML, truncated PNG, 100 MP bomb, 45 MP → 400 on both
routes, and nothing written. A valid PNG → re-encoded file written. NOT verified on the live stack: the backend image
wasn't rebuilt (no docker compose in lane B), so this needs `docker compose build backend && docker compose up -d backend` after merge.
