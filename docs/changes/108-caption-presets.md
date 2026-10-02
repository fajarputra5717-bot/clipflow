# 108 · Per-clip caption presets + "Apply to all clips" (P1 editor commit 2) · main.py, worker.py, index.html, shared/edit_spec.py, scripts, tests/ui

**Now.**
- `clip_candidates.edit_spec` JSONB (shared/edit_spec.py; NULL = today's behaviour). First key: `caption =
  {style, animation}`, validated against the make_ass() names. `PATCH …/candidates/{cid}` merges `edit_spec`
  (a key sent as null is removed; unknown key / style / animation → 400).
- Worker: `process_candidate_task` overlays the clip's `edit_spec.caption` on the job style + animation for
  every render of that clip (preview, final, thumbnails); font/size stay job-level; logged.
- UI (Captions tab): six preset cards = fixed pairs (Karaoke = outline+karaoke, Word pop = impact+word_pop,
  Hormozi = hormozi+bounce, Clean = clean+fade_settle, Neon = neon+typewriter, Boxed = boxed+word_pop), tiles
  drawn with the real style colours; picking one sets the clip's Font style / Animation selects (still the
  custom option); Apply stores the pair as the clip's preset, or clears it when it equals the job style; the job
  PATCH keeps the job's own style. "Apply to all clips in this job" → `POST /api/jobs/{id}/caption-preset`:
  job style + animation, every clip override cleared, clips in review re-render (finished clips need a new
  final; the confirm says so).
- Versions: snapshots include `edit_spec`; restore puts it back (pre-108 snapshots keep the current spec).
- Mirror: `SUBTITLE_STYLE_PREVIEW` had drifted from make_ass() (hormozi size 1.35→1.4, impact outline 4→2 +
  shadow, pastel outline 1.5→1); fixed, and `scripts/check_caption_mirror.py` now checks colours, outline,
  shadow, box, size, animation names and presets.
- Tests: `presets.spec.js` (card → selects → Apply sends `edit_spec.caption`, job style unchanged); edit and
  presets specs run with reduced motion (the taller drawer made Playwright's scroll animate under suite load,
  never settling, via `html{scroll-behavior:smooth}`); `/api/activity` fixture.

**Verified** on the stack: IME clip 1a9833d4 with Neon → its preview ASS has the neon colours + typewriter
tags, the sibling keeps outline + karaoke; "apply to all" (clean + fade_settle) → job style changed, override
cleared, only the review clip re-queued, version snapshot holds the old preset; invalid animation → 400; job
restored to outline + karaoke. UI: cards light/dark with the selected outline; harness 26/26 twice; mirror OK.
