# ui-phase2 c43afce (UI phase 2, Lane A pages, change 223) — live on staging :8080/:8001 (backend + frontend from it, worker = lane-b)

Measured as lane-c-a (member) and lane-c-b with Playwright at 1280×800, 1440×900 and 390×844, light + dark; admin-only and edge parts through Lane A's mocked specs served from `git archive origin/ui-phase2` (my own run).

## Cross-user / API (requested)
- **Watermark rename `PATCH /api/assets/watermarks/{id}`:** lane-c-b on lane-c-a's asset → **404** (also with an empty name, so ownership is checked first); lane-c-b DELETE on it → 404; unauthenticated → 401; non-UUID and all-zero id → 404; lane-c-b's list never shows it. Owner: name is trimmed and whitespace-collapsed ("  My   mark\n\n QA  " → "My mark QA"), 300 chars stored as 80, empty/blank → 400, missing field → 422. A name `<img src=x onerror=alert(1)>` is stored as text and rendered escaped in the sheet (0 injected nodes, 0 dialogs).
- **`/api/track` `.daily` counts only the caller's own views:** DB `clip_post_views` has snapshots for lane-c-a (45,000 + 41,000), lane-c-b (41,000 ×2 for one post), qa_a and qa-tmp-a. API: lane-c-a daily total 86,000 (peak day 2026-10-07), lane-c-b 41,000 (the duplicate snapshot of one post is not double-counted); neither includes the qa users' views; each total equals that user's Views tile.
- **Campaign payout write** (`PUT /api/campaigns/{slug}`, used by Set payout): a member PUT of the unchanged rules → 403 "Only an admin can edit campaigns" (lane-c-a and lane-c-b); unauthenticated 401. The mocked spec asserts the PUT body = payout {IDR, per_block, block_views, max_paid_views_per_video} and the other rules ("#x" hashtags) kept, and validation messages ("Enter the number of views (a whole number).").
- `tests/test_track.py` OK.

## Per page (live, member)
- **Campaigns (ef2e86e):** 3 cards, each with a bar (also "No cap set"); the card opens its campaign on a click anywhere on it and on Enter on the title link (`#campaign/fandra-octo`); IME (ends today / 1 day left) is highlighted amber; "Payout not set yet" is plain text for a member (no Set payout, no New campaign button: admin-only, verified in the mocked spec). No overflow at 390/1280.
- **Auto-import (f18c846):** Recent imports renders; lane-c-a's two rows are "Skipped · Under 5 min" (not confirmable) and "Already imported", so no Import anyway button appears (correct); "Import anyway" and "See all (8)" / "Show fewer" (5 shown) pass in the mocked spec only.
- **Analyze (69ea6d8):** Start analysis is a sticky bar ending 12 px above the dock at 1280 and 390 (716 vs 728, 772 vs 784), 44 px button; one "More layouts soon" tile.
- **Schedule (a5c1d13):** neutral week arrows (transparent, neutral text) in light; Mark posted = primary blue, Drop = quiet (transparent); 9:16 thumbnails (72×128); one reminder line ("… Telegram chat, which isn't set up yet"). Drop → toast "Dropped “…” from the schedule. Undo" with **no request for 5 s**; Undo → no PATCH and the post stays planned in the DB; without Undo the `PATCH {"status":"dropped"}` goes out 5.1 s after the click and the row is gone after reload.
- **Publish (2e8f110):** captions wrap at ~70 characters; to-post platform chips are filled primary (white on blue) while posted chips are pale green/amber; the campaign filter dropdown is absent here (only one campaign has clips), seen in the mocked spec.
- **Track (7a1ee84):** table headers and row cells share the same x positions (Campaign 70, Posts 309, Views 357 at 1280; 49/104/171/266 at 390); "VIEWS PER DAY · LAST 30 DAYS" area chart with peak label (86.000) and date range (15 Sept – 14 Oct).
- **Watermarks (af09534):** preview = the mark's alpha-cropped pixels (54×22 / 47×19) on a 9:16 sample frame (184×327 / 158×281); Rename: Esc cancels (no request), Enter sends the PATCH and updates the name; Delete removes it (confirm, DB row gone).
- **Settings (268167e):** four equal tabs Posting / Sounds / Watermarks / System (170×40 desktop, 82×44 phone); search finds settings across sections ("hashtag", "watermark opacity"); platform select is 184/332 px and not truncated; Discard changes is disabled until a real change (CLIPS_PER_JOB), enabled after, and restores the value without a PUT.

## Specs (my run of Lane A's changed specs on the served ui-phase2 copy)
analyze, auto-import, campaigns(-p2), phase-shots, publish, schedule-view, settings(-p2/-scope), sfx, touch, track, users, watermarks-p2, desktop + mobile: **125 passed, 3 skipped, 0 failed.**

## Findings (Low only)
- The 30-day chart puts a post's whole cumulative views on the day of its only snapshot (all 86,000 on 7 Oct), because there is no earlier baseline; correct per the data, but a new user's chart will look like one spike.
- Campaign card title links measure 25 px high (the stretched link covers the whole card, so the hit area is fine).

## Not verified
Admin view (New campaign, Set payout) and Import anyway / See all live (mocked only); the Publish campaign filter with ≥ 2 campaigns live; real-hardware frames; before/after screenshots (Lane A's folder, not reviewed).

Merge: OK for ef2e86e..c43afce.

## Addendum: 1863393 (chart baseline fix) — closed
Unit: `tests.test_track` 7 OK (incl. DailyViewsPostedTest). Live (staging backend rebuilt): lane-c-a daily total 86,000 = tile, lane-c-b 41,000 = tile, still own views only. The 7 Oct spike is still there for lane-c-a on purpose: both of its counted posts (tiktok 45,000 and instagram 41,000) were posted on 7 Oct, so with the new rule their first count belongs to that day. A post posted BEFORE the window (baseline) could not be built live (no direct DB inserts); it is covered by the unit test.

Merge: OK for 1863393; ui-phase2 (ef2e86e..1863393) is Merge OK from me.
