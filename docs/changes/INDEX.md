# Change log index

One line per change, newest last. Open the matching
`NNN-<slug>.md` only when you need the reasoning behind a change
you're about to touch.

Format: `NNN · YYYY-MM-DD · title · files touched`

<!-- entries start; append below this line -->
000 · 2026-09-26 · Rebuild baseline after VM loss (v2.1100 code, rebuilt infra + schema) · all (R-01 re-verified 2026-09-29)
001 · 2026-09-29 · R-02 runtime settings: DB→env→default everywhere, 5 s cache, dead settings wired · shared/settings.py, main.py, worker.py, index.html
002 · 2026-09-29 · R-03 X-ClipFlow-Key auth on /api/*, CORS origin list, signed media tokens for img/video · main.py, index.html
003 · 2026-09-29 · Move app folder /opt/riftstorm → /opt/clipflow (project name/volumes unchanged, symlink kept) · scripts/*.sh, CLAUDE.md, START-HERE.md, cron
004 · 2026-09-29 · R-20 AI provider abstraction: one ai_generate_json(), typed transient/permanent errors, no behaviour change · shared/ai/*, shared/errors.py, main.py, worker.py
005 · 2026-09-29 · R-21 Claude provider: strict tool-use structured output, Sonnet 5.5 hooks / Haiku 4.5 utility · shared/ai/claude.py, shared/settings.py
006 · 2026-09-29 · R-22 AI failover: per-task provider gemini|claude|auto (default auto), backoff+jitter, breaker 3→60 s, hook_provider · shared/ai/router.py, main.py, worker.py
007 · 2026-09-29 · R-01 fix: pin opencv <5 (v5 removed readNetFromCaffe; face detection silently fell back on every render) · worker/requirements.txt
008 · 2026-09-29 · R-04 facecam: zoom 0.78, min crop 120 px@1080p scaled, centering floor (>=60% and >= face) · worker.py, shared/settings.py
009 · 2026-09-29 · R-05 per-job watermark size/opacity (+ post-Submagic overlay); fixed edit panel resetting/ignoring subtitle style · main.py, worker.py, index.html
010 · 2026-09-29 · R-06 Submagic uploads a cached clean plate (no subs, no watermark); render_vertical stages optional · worker.py
011 · 2026-09-29 · R-07 stage timings, yt-dlp capped to H.264 ≤1080p, faster-whisper medium int8 (hf_cache volume) · worker.py, docker-compose.yml, Dockerfile
012 · 2026-09-29 · yt-dlp: "--" before the URL (audit 060 option injection) + 3 attempts with backoff on transient errors · worker.py
013 · 2026-09-29 · R-19 display caption fonts: shared/fonts.py catalog, Bold=0 + weight via name, emoji stripped, fonts served at /fonts/ · shared, worker.py, main.py, index.html, compose
014 · 2026-09-29 · R-08 cancel job: API + CancelWatch kills ffmpeg/yt-dlp, stops Whisper per segment; Cancel buttons · main.py, worker.py, index.html
015 · 2026-09-29 · R-09 burn_subtitles toggle: no make_ass + no subtitle stage when off; edit-panel checkbox · main.py, worker.py, index.html
016 · 2026-09-29 · R-10 browser-safe mp4: H.264 High cap, yuv420p, AAC, faststart; Range 206 verified; plays in Chromium + WebKit · worker.py
017 · 2026-09-30 · R-14 disk guards (reserve, yt-dlp pre-flight, 507), retention sweep per source video, orphan sweep (dry run) · worker.py, main.py, index.html
018 · 2026-09-30 · R-15 heartbeat + stale-claim reclaim, transient/permanent failures with backoff, Retry for jobs and candidates · worker.py, main.py, shared/errors.py, index.html
019 · 2026-09-30 · R-16 one watermark geometry (alpha bbox, get_watermark_rect), caption-top collision moves the watermark up, WATERMARK_WIDTH 320 · worker.py
020 · 2026-09-30 · R-17 WATERMARK_POSITION_Y 25 % + SUBTITLE_SEAM_GAP 1.5 %, stored per job at creation (NULL = legacy) · worker.py, main.py, settings
021 · 2026-09-30 · ffmpeg render watchdog: max(300 s, 10× clip) timeout, killed + transient → R-15 retry · worker.py
050 · 2026-09-29 · R-12 Left sidebar (collapsible column / mobile drawer) replaces right rail; Import options in one disclosure · index.html (v2.1102)
051 · 2026-09-29 · R-13 ui-audit.md; tabs pill docks via transform/opacity with 64/48 hysteresis (one scroll handler); job island is its own capsule with stage + % · index.html (v2.1103)
052 · 2026-09-29 · R-11 Motion 100–200/300–500 ms, setBusy() for every async button, edit drawer progressive disclosure + sticky glass action row, reduced-motion covers JS loops, keyboard tabs · index.html (v2.1104)
060 · 2026-09-29 · Security audit 001: threat model + findings (TASKS-4-SECURITY T1, lane B) · docs only
061 · 2026-09-29 · Status badges: semantic colours, WCAG AA in both themes (UI-QA T6, lane B) · index.html
062 · 2026-09-29 · One rotating chevron + aria-expanded for every disclosure (UI-QA T5, lane B) · index.html
063 · 2026-09-29 · YouTube URL allowlist + strict upload re-encode (audit-001 F4/F5, lane B) · main.py
064 · 2026-09-29 · R-19 prep: SIL-OFL caption fonts in worker/fonts (files only, lane B) · worker/fonts
065 · 2026-09-29 · libass spike = R-18 done: effects + variable-font weights, tests/libass-spike (lane B) · tests
066 · 2026-09-29 · Telegram notifier service, outbound-only (lane B; compose wiring in main) · notifier/
067 · 2026-09-29 · Motion & detail system (HIG UX pass) (lane B) · index.html
068 · 2026-09-29 · Sidebar = navigation; Settings/Watermarks as sheets; ClipFlow mark (lane B) · index.html
069 · 2026-09-29 · Settings sheet: inset lists, search, secret reveal, inline save state (lane B) · index.html
070 · 2026-09-29 · Import card: validated Analyze, instant thumbnail, one empty state (lane B) · index.html
071 · 2026-09-29 · Watermark library: checkerboard tiles, spring ✓, drag-and-drop, delete with undo (lane B) · index.html
072 · 2026-09-29 · Toolbar: iOS large title (continuous), bottom tab bar, no tabs pill (lane B) · index.html
073 · 2026-09-29 · Dynamic Island, Apple-style (springs, split, ready/failed events) (lane B) · index.html
074 · 2026-09-30 · Import job cards keyed + patched in place, smooth bars, status-line fix, Details disclosure · index.html
075 · 2026-09-30 · Job list own section, calm card motion (only the running job moves), 390 px overflow fix · index.html
076 · 2026-09-30 · Clickable campaign flow preview incl. Editor step (mock data, static page) · flow-preview.html
