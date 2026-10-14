# 223 — UI task phase 2 (Lane A pages): Campaigns, Auto-import, Analyze, Schedule, Publish, Track, Watermarks, Settings

Owner UI task 2026-10-14, phase 2 (Lane B did Review, Editor, Sound effects in 221). One commit per page.
Before/after: /opt/clipflow/docs/ui-recordings/phase2/{before,after} (1280×800, 1440×900, 390×844, light + dark;
tests/ui/specs/phase-shots.spec.js, now incl. the Watermarks sheet).

- **Campaigns** (ef2e86e): New campaign in the title row (a + on phones); the whole card opens the campaign (title link
  stretched over the card: mouse, touch, keyboard; no Details button); a campaign or posting week ending ≤ 2 days is
  highlighted ("Ends in 2 days" / "W2 closes today"); "Payout not set yet" = Set payout (admins) → a payout form on the
  campaign page (Per post / Per block / CPM, currency, amount, views, optional max) → PUT rules with the new payout
  section, the rest of the rules kept, wording still from payouts.describe; the budget / cap bar is on every card
  ("No cap set" when there is none). Shorter Campaign / Analyze / Publish intros (one line at 360, QA Low).
- **Auto-import** (f18c846): Import anyway on skipped items the rules couldn't vouch for, in Recent imports; the list
  shows the latest 5 with See all / Show fewer.
- **Analyze** (69ea6d8): Start analysis = a sticky bar above the dock; the three Coming soon layouts = one small tile;
  the campaign hint says what the campaign fills in (layout / language / clip count keep their from-campaign tags).
- **Schedule** (a5c1d13): one reminder line (the list's own); neutral week arrows (a button group, not a toggle); Mark
  posted primary, Drop quiet with a 5 s Undo (PATCH when the toast expires or the page closes); 9:16 thumbnails 72×128
  (56×100 phone); past days with nothing planned on one line.
- **Publish** (2e8f110): captions ≤ 70ch per line; the campaign filter is a dropdown like Review's; a chip still to post
  is the primary action (white on --seg-on, ≥ 4.5:1 in both themes).
- **Track** (7a1ee84): one subgrid for header + rows (names left, numbers right, amounts never wrap; phones: name on its
  own line); a views-per-day line chart for the last 30 days. Backend: GET /api/track `.daily` =
  `shared/track.daily_views()` over the caller's own clip_post_views (window + each post's baseline): per post the day's
  highest count carried forward, new views = the rise (never negative), summed per WIB day. SVG, role=img + summary.
- **Watermarks** (af09534): preview = the mark's visible pixels (alpha-cropped in a canvas, like get_watermark_rect)
  on a sample 9:16 frame at your Watermark width / height settings; rename + delete per tile. Backend:
  PATCH /api/assets/watermarks/{id} {filename} (own rows, 404 otherwise).
- **Settings** (268167e): Posting / Sounds / Watermarks / System sections with a side menu (equal tabs on phones), one
  section at a time, search across every section, last section remembered; the platform select fits its labels;
  Reload → Discard changes (enabled only with changes).

Deploy: backend (track daily + watermark rename) → frontend is live on merge. No schema change.
