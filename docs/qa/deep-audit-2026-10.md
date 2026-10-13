# Deep QA/QC audit — 2026-10-13 (staging a26b041 for anything that wrote; production read-only)

Method: Playwright against staging :8080 as lane-c-a (own data only) at 390/768/1280/1440 on all 8 steps + Settings/Watermarks sheets; rAF frame timing, longtask + layout-shift observers, CSSOM keyframe scan, reduced-motion emulation, a Playwright trace (390), editor video/timeline probe, mocked-500 error states; unauthenticated sweep of every OpenAPI route; per-endpoint latency (15 calls each); read-only prod docker/psql/log checks. No prod writes, no restarts.

## Critical
None.

## High
1. **[B] The editor preview can never be heard.** `frontend/html/editor/editor.js:107`: `<video id="edVideo" … loop muted …>`, and no mute/unmute control exists (grep: no `.muted =` or toggle). Playback does decode audio (webkitAudioDecodedByteCount > 0), so the clip has sound, but nothing in the Audio tab (Loud & punchy, SFX, silence trim, compression) or the filler/cut edits can be auditioned before Render. Repro: open `#editor/<job>/<clip>`, press ▶: silent, no speaker control. (If intentional, still add an unmute; Medium then.)

## Medium
2. **[A] Closed job overlay is a live keyboard stop.** `#jobOverlay` is `visibility:visible; opacity:0; pointer-events:none`, not `hidden`/`inert`, so Tab reaches its invisible × button (`#jobOverlayClose`, 25×25) after 9 stops and screen readers read "Running jobs / No jobs running". Breaks the CLAUDE.md rule "every closed overlay layer must be visibility:hidden". Repro: any step, press Tab 9×; focus disappears.
3. **[A] Phone touch targets < 44 px** (390): Settings inputs 34–36 px high (`#set-*`, `#reminderLead`), editor switches `.ed-switch` 42×26 and `.ed-sw-sm` 26×26, editor number input 40 px high, `.ai-switch` 51×31. At 768 many controls are 34–36 px (appbar icon buttons, account button, import choice chips, Review filters). My box measure cannot see `::before` hit areas, so some may already be padded: confirm with a real touch test.
4. **[A] Layout shift on first paint ~0.1.** Initial-load CLS 0.108 at 768, 0.095 at 1280, 0.039 at 390; hash switch import→review shifts `#rvBody` 0.084 at 390. Near the 0.1 limit; cause = content inserted after the API reply with no reserved height.
5. **[A+B] Publish/Schedule/Track show the raw server detail as the error** ("boom" for a mocked 500; for a real one "Internal Server Error") with no "Couldn't load … Retry" lead. Review and Editor handle it well ("Can't load the review list: …", "Can't open this clip: … Back").
6. **[Ops] Container logs hold only what happened since the last redeploy.** Backend log has 0 5xx but only since today's recreate, so the requested 7-day log audit is impossible; every deploy wipes history. nginx logged 15 "connection refused" upstream errors on 10-12 15:58–16:39 (backend restarting during deploys: brief 502s to the user). Suggest a persistent log driver; a rolling deploy order is already in place.

## Low
7. **[B] Editor keyboard:** no Space/arrow seek on the timeline; only trim handles take arrows; the play button must be focused to use Space. (Seek by click is accurate: clicks at 100/300/600 px → 1.00/3.00/6.00 s; a click inside a removed range snaps to its start.)
8. **[A] Non-compositor animations:** keyframes `badgeShimmer`, `shimmer`, `aiShine`, `shine`, `sweep`, `flow` animate `background-position`; `aiGlow`, `analyzeGlow` animate `box-shadow`. They only run on running/idle-AI items (0 animations active on every idle page), no layout properties, no `transition:all` or layout-property transitions anywhere in CSSOM. Reduced motion: 11 rules in index.html, 2 in editor.css, 1 in editor.js, 0 in review.js and tokens.css; with `prefers-reduced-motion` emulated, 0 animations ran (same as without: effect not provable on an idle page).
9. **[A] Desktop Settings/Watermarks sheet open drops frames** at 1280: 8 frames > 34 ms, worst 67 ms (headless software compositing, 4 audit runs were not parallel for this one); 390 is clean (worst 33 ms). Page switches, review scroll (12 wheel steps), and editor scrub all 0 frames > 34 ms, 0 long tasks.
10. **[A] FastAPI `/docs`, `/redoc`, `/openapi.json` are open on the prod backend :8000** (127.0.0.1 only; through nginx they fall back to index.html, verified). Lists every route unauthenticated if :8000 is ever exposed. Disable in prod (`docs_url=None`).
11. **[A] Session lookup scans:** `user_sessions` 33,981 seq scans vs 3,021 index scans (17 rows, harmless today); `/api/activity` costs 15 DB transactions per call (empty), `/api/review/clips` 19, editor state 21: no per-row N+1 (counts flat for 2 jobs / 34 clips) but many connection checkouts per request. The activity poll runs with the job monitor.
12. **[A] Retention:** `/data/downloads` 14 GB (14 % of a 391 GB disk, 323 GB free); 8 sources downloaded, 1 purged; orphan sweep stays dry-run by default.

## Passed (no finding)
- No horizontal scroll at 390/768/1280/1440 on any step or sheet; 0 page/console errors; every Tab stop (10 per view) shows a focus ring; no unlabelled interactive element (my first 'nolabel' hits were aria-labelledby false positives).
- Auth: unauthenticated sweep of 84 paths / 101 operations: only `/`, `/health`, `/api/env`, login, logout answer without a session (by design).
- Latency (staging, 29 GET endpoints, 15 calls, 2 jobs/34 clips): p95 ≤ 40 ms, p50 ≤ 38 ms; slowest = schedule-plan 40, editor/timeline 30, job detail 34. DB is 11 MB (68 versions, 46 clips): EXPLAIN on the top queries would show seq scans by design at this size.
- Production: 0 restarts everywhere; 0 stuck jobs (none non-terminal > 1 h), 0 failed/never-previewed clips, no `attempts` > 0; worker 190 MiB, backend 57 MiB; 7,841 backend requests in the available log: 7,841×200/23×206/2×401, no 5xx; notifier/sender log healthy (message_ids 1762, 1763 sent).
- Editor playback: video 33.8 s = ffprobe 33.814 s, 540×960, 0 dropped frames over 272, playhead advances with `currentTime`, ▶ ↔ ❚❚ label.

## Not verified
- Production UI at 4 widths (no QA token, owner decision); real-device touch and Safari/iOS; a Chrome DevTools frame trace (Playwright trace of the 390 run is at scratchpad `ui/trace-390.zip`, no screenshots).
- Cross-user sweep this round (only lane-c-a exists in my credential file; a second member needs an admin reset I'm not approved for); last full run: see earlier gate/e2e docs.
- Every inspector control end to end and preview-vs-final match this round (covered in the 4eb1f06, 8fdbdc1, f8219ec, fresh-e2e docs); yt-dlp failure rate and per-stage render times (worker logs reset on deploy; a staging preview of a 34 s clip took ~13 s).
- Memory/CPU peaks (point samples only), 7-day error history, EXPLAIN on prod-size data.
