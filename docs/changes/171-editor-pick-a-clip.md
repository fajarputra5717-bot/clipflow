# 171 · Editor with no clip = "Pick a clip" (shell item 4, 2026-10-09)

- Editor in the pill: the classic drawer when its panel is open; else the last opened clip (remembered per user,
  `clipflow_last_clip_<user id>`, set on every `#editor/<job>/<clip>`); else `#editor` = Pick a clip.
- Pick a clip = compact Review grid in `#pickSection`: the same saved filters (GET/PUT `/api/review/filter`), clips
  from `/api/review/clips` (expired left out), each card a link to `#editor/<job>/<clip>`. The Editor step is never
  disabled now; the old job list ("Tap a job to review…") is never shown for it.
