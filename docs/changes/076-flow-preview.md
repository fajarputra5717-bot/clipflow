# 076 — Campaign flow preview (lane B, 2026-09-30)

Static, clickable mock at `frontend/html/flow-preview.html` (served at `/flow-preview.html`)
for approving the planned campaign workflow before any backend work:
Campaign → Auto-import → Analyze → Review → Schedule → Publish → Track.

- Mock data only, no `api()`/`fetch()` calls, no auth; "Preview — mock data" pill in the toolbar.
- Tokens copied from index.html `:root` + dark block (067 motion, 052/061 badges); same
  `clipflow-theme` localStorage key. Keep in step if the app tokens change.
- Covers: brief → extracted rule chips (sheet, closed = hidden/inert), source channels with
  auto-import switch, job options (Language Auto/EN/ID, 4 layouts with 9:16 mini previews),
  review with hook reason, karaoke caption preview and rule-check gating (fix → approve),
  schedule in viewer TZ with 7/8:30/10 pm ET slots + WIB, per-platform publish queue,
  performance (views × CPM / 1000, capped per clip and by budget).
- Reduced motion: CSS rule + `motionMs()`/`scrollMode()`; caption loop stops.
- Verified in headless Chromium at 1280 (light) and 390 (dark, reduced motion): every step
  clicked through, no console errors, no horizontal page scroll.
- Not wired into index.html navigation; nothing in the real app changed.

## Editor step (added in the same change, before approval)

New step 5 "Editor" between Review and Schedule (flow is now 8 nodes; Review cards get
"Open editor"). Second `<script>` block in the page, mock only:
- 9:16 player driven by one rAF loop (`tick`/`paint`): chunked captions (≤3 words, never across a
  sentence) in the chosen preset, keyword colour, hook title card for the first 2–3 s, auto-zoom
  punch-ins on keywords (intensity), progress bar, transition + SFX badge at each cut, watermark.
- Timeline: waveform, word chips (click = seek), struck-through silences/fillers (click = restore),
  ◆ zoom markers, draggable trim handles (pointer + arrow keys), output length feeds the length rule.
- Inspector: Captions · Effects · Audio · Watermark · Export segmented control with a spring
  thumb (`--seg-thumb` token) and directional spring panel transitions; arrow-key tab nav.
- Watermark picker None / library assets / Job default with position/size/opacity; "Campaign requires
  no watermark" warning + Set to None. Virality chip; sticky footer Render preview / Approve & schedule
  (disabled until all rules pass).
- Reduced motion: no autoplay (manual play only), static preset tiles, CSS motion collapsed.
