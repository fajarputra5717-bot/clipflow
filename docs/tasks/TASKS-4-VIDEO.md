# ClipFlow — stream: VIDEO OUTPUT

Segmented task stream. Companion streams: `TASKS-4-UIUX.md`,
`TASKS-4-SECURITY.md`. Work one stream at a time; don't interleave.

Read `CLAUDE.md` and `docs/changes/INDEX.md` first. Grep for function
names — **do not trust line numbers**, the file has moved a lot.

Ground rules unchanged: one task = one commit, `docs/changes/NNN-<slug>.md`
+ INDEX line, schema via `ensure_schema()`'s `statements` list, settings
via `DEFAULT_SETTINGS`, compile checks before commit, honest "what I did
NOT verify" notes.

---

## P0 — HOTFIX: backend is crash-looping right now

`riftstorm-backend` will not boot. Repeating traceback:

```
File "/app/app/main.py", line 1905, in <module>
    @app.post(
...
RuntimeError: Form data requires "python-multipart" to be installed.
```

Two endpoints declare `UploadFile = File(...)` — the manual thumbnail
upload and `upload_watermark_asset`. FastAPI needs `python-multipart`
to build those routes, and it raises at **import time**, so the whole
app dies before serving anything. uvicorn then restarts and dies again.

Fix: add `python-multipart` to the backend's `requirements.txt` and
rebuild the image. A `pip install` inside the running container is a
temporary unblock only — it will not survive the next rebuild, so add
it to requirements either way.

Verify the container actually stays up (`docker compose ps`, then hit
`/health`) before starting Task 1. Commit this alone.

---

## Task 1 — Watermark / subtitle collision (root cause found, verify it)

**Symptom:** the watermark renders on top of / immediately against the
caption, both crowded at the seam between the gameplay pane and the
facecam pane.

**Root cause — confirm before fixing.** Two separate defects compound:

1. **The watermark position is hardcoded to canvas dead-centre.** In
   `render_vertical()` the overlay filter is literally:
   `overlay=(W-w)/2:(H-h)/2`. On a 1080×1920 canvas that puts the
   watermark's centre at y=960. For a 70:30 split the seam is at
   y=1344, so the watermark sits in the lower third of the gameplay
   pane — exactly where captions live.

2. **The existing anti-collision clamp in `make_ass()` measures the
   wrong edge.** It computes `safe_margin_v` from the watermark's
   bottom and does `margin_v = min(margin_v, safe_margin_v)`. But ASS
   `MarginV` with `Alignment=2` is the distance from the frame bottom
   to the **bottom of the text**, and text stacks **upward**. The
   clamp therefore protects the caption's bottom edge while the caption
   grows up into the watermark. It also never fires in the common case:
   at 70:30 the seam-derived `margin_v` (~653) is already smaller than
   `safe_margin_v` (~803), so `min()` returns the seam value and the
   watermark check is a no-op. Tall presets (`hormozi`, size_mult 1.4)
   and multi-line captions collide every time.

**Fix:**

- Make the collision check use the caption's **top** edge:
  `caption_top = canvas_height - margin_v - estimated_text_height`,
  where `estimated_text_height ≈ effective_size × line_count ×
  line_spacing`. You'll need a line-count estimate — either the max
  lines across the segments being rendered, or a conservative constant
  of 3. State which you chose and why.
- Compute the watermark's real rect (x, y, w, h) once, in one place,
  and have both the ffmpeg overlay and the ASS margin logic read from
  that same function. Right now the geometry is duplicated and the two
  copies disagree. This is the actual structural fix — do it even if
  nothing else in this task lands.
- Assert non-overlap. If the rects intersect, resolve deterministically
  (documented order of preference) rather than silently rendering a
  collision. Log when a resolution fires.

**Acceptance:** at 60:40 **and** 70:30, with the `hormozi` preset and a
3-line caption, the caption never touches the watermark rect. Verify by
rendering and **looking at actual frames** (`ffmpeg -ss … -vframes 1`),
not by reading the filter string.

---

## Task 2 — New default positions: watermark up, subtitle down

Current defaults put both elements in the same band. Separate them.

- **Watermark:** move to roughly 20–30% of canvas height (well up in
  the gameplay pane), not 50%. Pick the exact value by rendering and
  looking. It must stay clear of the platform safe zones if phase-2
  task 6 landed — check `docs/changes/` before choosing.
- **Subtitle:** move **down**, closer to the seam. The current 4%
  `seam_gap` leaves ~77px of dead space at 70:30. Tighten it, but the
  caption must still never cross into the facecam pane and cover the
  creator's face — that was a previously-fixed bug, don't regress it.
- Both become **settings with the current behaviour as a documented
  fallback**, not hardcoded constants: `WATERMARK_POSITION_Y` (percent)
  and a subtitle offset knob, in `DEFAULT_SETTINGS`.
- **Do not change existing jobs' output.** New defaults apply to new
  renders; jobs with an explicit stored position keep it.

---

## Task 3 — Manual watermark + subtitle position editor

Give the user direct control, with a real preview, committed through
the existing Apply-changes flow.

**Data:**
- `jobs.watermark_pos_x` / `watermark_pos_y` (percent, nullable)
- `jobs.subtitle_pos_y` (percent, nullable)
- `NULL` = "use the computed default", so existing rows are untouched.

**Backend:** `render_vertical()` and `make_ass()` read these when set,
falling back to the Task 1/2 computed geometry. The Task 1 non-overlap
assertion still applies — if the user drags them into each other, warn
in the UI, but **honour what they chose**; don't silently override a
manual position.

**UI — the overview is the point.** Inside the existing
`.preview-frame` (already `position: relative`, with absolutely
positioned children — use that):

- Overlay two draggable guide boxes on the video preview: one for the
  watermark (real aspect ratio, real relative size), one showing the
  caption band.
- Drag to reposition; percentages update live. Also expose numeric
  inputs for precision.
- Show the seam line and, if implemented, the platform safe zone, so
  the user can see what they're avoiding.
- Highlight the boxes in red when they intersect.
- A "Reset to auto" control that clears back to `NULL`.
- Nothing re-renders on drag. Changes stage locally and commit on
  **Apply changes**, exactly like every other edit — `applyEdits()` is
  where this belongs.

**Honesty note for the changelog:** the overlay is a *positional*
approximation — it shows where things sit, not a pixel-exact render of
the final ASS output. Say so in the UI in one short line, and don't
claim WYSIWYG.

---

## Order

P0 (the crash) → 1 → 2 → 3.

Task 1 is the one that matters. Tasks 2 and 3 are cosmetic if the
geometry is still computed in two places that disagree.
