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
077 · 2026-10-01 · Hook analysis uses the whole transcript (windows + ranking above 400k chars), per-call token logging · worker.py, shared/ai, shared/settings.py
078 · 2026-10-01 · Watermark never above 16 % (global floor, caption push-up warns) + pilot campaign fixtures (MotionKlip, IME Roleplay, Fandra Octo) · worker.py, docs/campaigns
079 · 2026-10-02 · Per-job language Auto/English/Indonesian (Whisper detect + fallback, prompts, Submagic), id/en stoplists · worker.py, main.py, index.html, shared/languages.py
081 · 2026-10-02 · Campaign flow v1: rules files → jobs.campaign, watermark preset, hashtags, prompt context, rule skips, badge + filter · main.py, worker.py, index.html, shared/campaigns.py
082 · 2026-10-02 · Edit drawer tabs: Captions / Effects (soon) / Audio (soon) / Watermark / Export · index.html
083 · 2026-10-02 · Captions keep karaoke: override only for real edits, word-aligned re-timing, 16 redundant overrides cleared (QA #1, #3) + karaoke word spacing · worker.py, index.html
084 · 2026-10-02 · Guards: hook window overlap < window (PUT 400 + worker clamp), API job language = WHISPER_LANGUAGE, rank negative id / non-numeric score skipped (QA #4 #5 #9) · main.py, worker.py
085 · 2026-10-02 · Retention engine merged from lane-b (silence trim + TimeMap re-timing, two-pass loudnorm, punch-in zoom builders; tests) · shared/retention.py
086 · 2026-10-02 · Final render loudness: two-pass loudnorm −14 LUFS, limiter −1 dBTP, video copied, ebur128-verified (QA #2) · worker.py
087 · 2026-10-02 · No-facecam layout: layout "none" + no-face fallback render full-frame gameplay, one shared layout graph (QA #6) · worker.py, main.py, index.html
088 · 2026-10-02 · Pin PyAV < 19: av 19 broke faster-whisper decode_audio (metadata_errors), every transcription would fail · worker/requirements.txt
089 · 2026-10-02 · Fix: first previews of new imports had no captions (083 regression: analysis passed the pre-transcription job row to create_preview) · worker.py
090 · 2026-10-02 · Progress rule: island is the only progress UI (CLAUDE.md + roadmap); GET /api/activity {kind, stage, percent, label} feeds it, background renders/Submagic now show · main.py, index.html
091 · 2026-10-02 · Loudness on previews + Submagic finals, failure keeps the file + render_warnings chip, 2× disk reserve (P0) · worker.py, main.py, index.html
092 · 2026-10-02 · Campaign watermark missing → no watermark + failing chip + WARNING log, never a silent fallback (P0) · worker.py
093 · 2026-10-02 · Campaign hashtags: exact order at the END; rules wording "required_in_order" (not "prefix") (P0) · docs/campaigns, shared/campaigns.py
094 · 2026-10-02 · Hook analysis window minimum 10 min (settings 400 + worker clamp) (P0) · main.py, worker.py
095 · 2026-10-02 · Facecam layout per job: majority (or position-agreeing tie) → panel for all, else full-frame for all; overrides logged; 9 jobs backfilled (P0) · worker.py, main.py
096 · 2026-10-02 · Full-frame clips: captions at FULLFRAME_CAPTION_Y (default 78 %, clamped 60–85) instead of the seam (P0) · worker.py, shared/settings.py, index.html
097 · 2026-10-02 · Card-level progress = island-style capsules (Import job cards, Publish rows); rule in CLAUDE.md (P0) · index.html
098 · 2026-10-02 · P0 cleanup: watermark height setting 16–85 %, WHISPER_LANGUAGE labelled "Fallback language", badge v2.1117 · main.py, index.html
099 · 2026-10-02 · Campaign watermark resolved at job creation; a miss is stored (jobs.watermark_failure) → no watermark + chip + toast, never a fallback · main.py, worker.py, index.html
100 · 2026-10-02 · Loudness verify acts: every output re-measured; >1 LU off or TP > −1 dBTP → one corrective pass (headroom + overshoot), still off → chip (pre-P1) · worker.py
101 · 2026-10-02 · Facecam tie rule: panel if the hit is in a corner/edge AND persistent (≥ 3 hits, spread ≤ 0.03), else full; reason logged (pre-P1) · worker.py
102 · 2026-10-02 · Island feed: activity errors keep last state + backoff, running-state allow-list, Submagic indeterminate (pre-P1) · main.py, index.html
103 · 2026-10-02 · Job creation clamps watermark height (setting and campaign preset) to 16–85 % (pre-P1) · main.py
104 · 2026-10-02 · Lane B Playwright UI harness on main (tests/ui, cherry-picked 556cca7); 22/22 pass · tests/ui
105 · 2026-10-02 · Island allow-list includes reanalyze_queued (102 Low); P1 backlog: compression before loudnorm · main.py, index.html
106 · 2026-10-02 · UI shell (a): flow-preview stepper as top-level nav (Analyze/Review/Editor live; P2/P3 steps disabled), "Publish" view → Review, gear for Settings · index.html, tests/ui
107 · 2026-10-02 · Visual system (b): flow-preview type scale, pill + fill buttons, panels (24 px, --shadow), inputs app-wide · index.html
108 · 2026-10-02 · Per-clip caption presets (edit_spec.caption) + "Apply to all clips", style mirror fixed + check script (P1) · main.py, worker.py, index.html, shared/edit_spec.py
109 · 2026-10-02 · Campaign rule chips (length per platform, hashtags, watermark) + Approve gate (UI + 409) + content-safety warning (utility AI) (P1) · shared/rule_checks.py, main.py, worker.py, index.html
110 · 2026-10-02 · Hook score stored (was never saved) and shown as "AI estimate" next to the reason; new hook clears it (P1) · worker.py, main.py, index.html
111 · 2026-10-02 · Keyword highlight: AI-picked (utility model, stoplists), tap to toggle, colour swatches, baked into the ASS in every mode (P1) · worker.py, shared/edit_spec.py, index.html
112 · 2026-10-02 · Per-clip caption position (edit_spec.caption_y, 30–85 %, never below the facecam seam) (P1) · worker.py, shared/edit_spec.py, index.html
113 · 2026-10-02 · Submagic "use as final" passes the same campaign rule gate as Approve (409 + disabled button) (QA Medium) · main.py, index.html
114 · 2026-10-02 · "Final outdated · re-render" chip after render-affecting changes (apply-to-all, job style/render options, per-clip apply, restore); cleared by a new final (QA Low) · main.py, worker.py
115 · 2026-10-02 · Campaign clips get their description at analysis (utility model, clip language) ending with the campaign hashtags; prompt + hashtag helper moved to shared · worker.py, main.py, shared
116 · 2026-10-03 · Keyword colour defaults to the first swatch that contrasts with the style highlight (yellow styles → green); user choice kept · worker.py, shared/edit_spec.py, index.html
117 · 2026-10-03 · Campaign default facecam layout (rules default_layout; IME = none), used unless you pick one · docs/campaigns, shared/campaigns.py, main.py, index.html
118 · 2026-10-05 · Facecam must be a persistent (≥ 50 % of frames), steady box in a corner/edge; game faces no longer give a junk panel (Lane C) · worker.py
