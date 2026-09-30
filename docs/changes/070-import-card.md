# 070 — Import card: validated Analyze, instant thumbnail, one empty state
Date: 2026-09-29 · Commit: see `git log --grep "070"` · Files: frontend/html/index.html · UI v2.1107

## What changed
- **Analyze** is now a primary filled button labelled "Analyze". It is **disabled until the URL passes
  `youtubeUrlProblem()`**, which applies the backend's `validate_youtube_url()` rules (063): https only; exact hosts
  youtube.com / www / m / music.youtube.com / youtu.be; no userinfo; port none or 443; no whitespace, control
  characters or backslash; no leading `-`. The link must also name a video (watch `v=`, `/shorts|live|embed/<id>`,
  youtu.be/<id>, 11-char id). The old, looser `validYouTube()` allowed any `*.youtube.com` and `http`; it now
  delegates to the same rules.
- A hint line under the field shows the specific problem (`aria-invalid` plus a red field edge), otherwise the
  accepted-hosts reminder. It updates on every input, including paste.
- **Thumbnail preview:** a valid link shows `https://i.ytimg.com/vi/<id>/mqdefault.jpg` with the id. It fades and
  lifts in (`--dur-3`) only after the image loads, and hides if it fails. The pulsing "analyze-ready" glow is gone
  (the enabled primary state carries that meaning).
- **One empty state:** the idle "Ready. Enter a YouTube URL…" status box and the "No active jobs." panel are
  merged into one "Nothing importing" empty state (icon + tip) in `#currentJobs`. `#createStatus` is now
  `hidden` unless it has something to say (Creating…, Job started, errors), and it hides again after the
  confirmation instead of resetting to "Ready.".
- The unexplained **"AI" chip is removed**. The card subtitle now says what the AI does.
- **Global `[hidden]{display:none!important}`:** author `display:flex` rules were un-hiding `[hidden]` elements. That
  broke 069's settings search (non-matching rows stayed visible) and left a gap for the hidden preview. This fixes both.

## Decisions & trade-offs
- The frontend is slightly stricter than the backend (it requires a video id) so the preview and the button agree.
  The backend accepts a bare `https://www.youtube.com/`, which can't produce a job anyway.
- The thumbnail request goes from the browser to i.ytimg.com (YouTube's CDN). This is the only third-party request the UI makes.

## Verification (headless Chromium, :8081, /api + i.ytimg.com mocked; light/dark × 1280/800/390)
0 errors. No clickability failures.
- 10 URL cases: empty, `http://`, `youtube.com.evil.com`, `youtube.com@10.10.10.1`, `:8443`, `--exec=id` and a bare
  host are disabled, each with its message. youtu.be, m./shorts and music. with `&list` are enabled and show the preview.
- The preview reaches `is-loaded`, opacity 1. The empty state renders once, and the old "Ready." is gone.
- Analyze with a mocked bad response shows the status box with the error, and the button returns to Analyze.
- The 069 search re-checked by rendered rects: exactly 3 rows visible.
- Under reduced motion, 0 running animations while typing a valid URL.
