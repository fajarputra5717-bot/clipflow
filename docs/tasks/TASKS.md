# ClipFlow — work order (7 tasks)

Read `CLAUDE.md` first. It already describes the architecture, the two
state machines, the schema-migration pattern, and the naming/queue
conventions — **do not re-read `worker.py` / `main.py` / `index.html`
end to end.** Every task below gives you the exact function or line
anchor to open. Use `grep -n` to jump; read only the surrounding
block.

## Ground rules (apply to all 7 tasks)

- **One task = one commit.** Work them in order, `git commit` after
  each with the message `feat(N): <short summary>` (or `fix(N):`).
  Don't batch multiple tasks into one commit.

### Change log — write one file per task

Keep a persistent, readable record of every backend/worker/frontend
change in `docs/changes/`. This is the memory a future session reads
instead of re-deriving intent from a diff.

After each task, create `docs/changes/NNN-<slug>.md` (zero-padded,
sequential — `001-facecam-zoom.md`, `002-watermark-size.md`, …) with:

```
# NNN — <title>
Date: YYYY-MM-DD · Commit: <short sha> · Files: main.py, worker.py

## What changed
<2–5 bullets, behavior-level not line-level>

## Why
<the problem this fixed — symptom, not just the fix>

## Decisions & trade-offs
<anything where you picked one option over another, and what you
rejected. Include defaults chosen and why.>

## Schema / settings added
<new columns, DEFAULT_SETTINGS keys, queue states — or "none">

## Gotchas for future changes
<what will break if someone touches this carelessly>

## Verification
<what you actually ran/checked, and what you did NOT verify>
```

Be honest in **Verification** — if something couldn't be tested
against a live DB, live Submagic key, or real video, say so plainly
rather than implying it was confirmed working.

Also maintain `docs/changes/INDEX.md`: one line per entry
(`NNN · date · title · files touched`), newest last. A future session
reads only INDEX.md first and opens a detail file on demand — that's
the point of the split, so keep INDEX lines to one line each.

`CLAUDE.md` stays a **condensed invariants doc**, not a history. Only
update it when a task changes something another session must know to
avoid breaking (new column, new setting, new queue state, changed
default) — and keep it under ~200 lines by condensing, never by
appending. History belongs in `docs/changes/`.

### Code conventions

- Schema changes go in `ensure_schema()` in `main.py` as one more
  entry in the `statements` list. It commits per-statement now; keep
  it that way.
- New runtime knobs go in `DEFAULT_SETTINGS` (`main.py`) — that dict
  is the whitelist, `PUT /api/settings` rejects anything not in it.
  Worker reads them via `setting(name, default)`.
- Don't hand-roll SQL for candidate updates; use
  `update_candidate(id, **fields)`.
- After each task, verify: `python3 -m py_compile main.py worker.py`
  and check the inline `<script>` in `index.html` parses
  (`node --check` on the extracted script).
- If a task needs a decision I didn't make, pick the option that
  changes the least behavior by default, put it behind a setting, and
  note the choice in the commit body **and** in the change-log file's
  "Decisions & trade-offs" section. Don't silently change defaults for
  existing jobs.

---

## Task 1 — Bigger, properly centered facecam

**Anchor:** `calculate_face_crop()` in `worker.py` (~line 2176), and
`detect_face_for_clip()` (~line 1765).

The bottom facecam pane is currently under-zoomed and the face drifts
off-center. The logic already exists but isn't tuned or reachable:

- `FACE_ZOOM_RATIO` (default `0.62`) is read from `os.environ` only.
  Move it to `setting("FACE_ZOOM_RATIO", …)` + `DEFAULT_SETTINGS` so
  it's tunable without a redeploy, and raise the default to ~`0.78`
  (face fills more of the pane).
- The `max_half_width` / `max_half_height` clamp shrinks the crop so
  it can stay perfectly centered. When the detected face sits near a
  frame edge that clamp can collapse the crop badly. Add a floor: if
  the clamp would reduce `crop_height` below ~60% of the requested
  height, prefer keeping the requested zoom and accept edge-clamped
  off-center framing instead of over-shrinking. Log when this happens.
- `max_crop_height = source_height * 0.55` may now be the binding
  constraint — re-check it's not what's capping the zoom.

**Keep** the existing `auto`/`left`/`right` layout hint working
exactly as it does today — this task only changes crop size and
centering, not which face is picked.

**Acceptance:** on a clip with a corner PIP webcam, the face fills
noticeably more of the bottom pane than before and is centered
horizontally; `layout=left` and `layout=right` still select the
correct side.

---

## Task 2 — Per-job adjustable watermark size

**Anchors:** `WATERMARK_WIDTH` / `WATERMARK_OPACITY` in `worker.py`
(~line 148), the watermark filter in `render_vertical()`, and the
edit panel in `index.html` (the `edit-section` blocks inside
`renderCandidate()`).

Today watermark width is a container-level env constant (`630`).
Make it per-job and adjustable *before* preview and final render:

- Add `jobs.watermark_width INT` and `jobs.watermark_opacity REAL`
  (nullable — `NULL` means "use the global default", so existing jobs
  are unaffected).
- Read them in `render_vertical()` via the job dict, falling back to
  the current constants. They must reach both `create_preview()` and
  `render_final_candidate()`.
- Add a size control (slider or number input, ~200–900px) + opacity
  to the edit panel, next to the subtitle style row. It must be sent
  by `applyEdits()` — that function is where every other edit gets
  committed, and it already re-renders the preview afterward, so the
  new value takes effect on the next preview without extra plumbing.
- Show a live indication of relative size in the preview panel if
  cheap to do; don't build a full compositor.

**Submagic output:** Submagic renders from the clip we upload, so a
watermark baked into the upload survives but can be cropped/zoomed by
their Magic Zooms. Apply our watermark **after** downloading their
render instead — in the `"applying"` branch of
`process_submagic_task()`, run one ffmpeg overlay pass on the
downloaded file before storing it as `final_path`. Pair this with
Task 3 (upload a clean plate).

---

## Task 3 — Stop double subtitles on the Submagic path

**Problem:** `process_submagic_task()`'s `"uploading"` branch uploads
`candidate.preview_path`, which already has ASS subtitles burned in
by `make_ass()` + `render_vertical()`. Submagic then adds its own —
two subtitle tracks on screen.

**Fix:** upload a clean plate, not the preview.

- Add a no-subtitle, no-watermark render path. There's already a
  precedent for exactly this composition in the still-frame helper
  around `worker.py` line ~4187 (gameplay-top / facecam-bottom, no
  subs, no watermark) — reuse that filter graph shape rather than
  writing a third copy.
- Render it on demand in the `"uploading"` branch (cache it as
  `<candidate_id>_clean.mp4` under `PREVIEW_DIR` so a retry doesn't
  re-render), upload that.
- Native (non-Submagic) renders keep burned-in subtitles exactly as
  today. This is not a global "turn subtitles off" switch.

**Acceptance:** a candidate sent through Submagic shows exactly one
set of captions (Submagic's). The same candidate rendered natively
still shows ours.

---

## Task 4 — Faster analysis

**Anchor:** `process_analysis_job()` in `worker.py` (~line 3658);
stages are `download` → `video_normalization` → `audio_extraction` →
`transcription` → Gemini analysis.

**Measure before optimizing.** Add per-stage elapsed-time logging
first (one `log()` per stage with seconds), run one real job, and put
the numbers in the commit body. Then optimize the stage that actually
dominates — probably transcription or download, but confirm.

Candidate levers, in rough order of payoff:

1. **Transcription:** `transcribe()` uses `openai-whisper`.
   `faster-whisper` (CTranslate2) is typically 3–4× faster on CPU for
   identical model sizes. Swap it behind the existing `WHISPER_MODEL`
   setting, keep the same `(transcript, segments)` return shape —
   including **word-level timings**, which `make_ass()` depends on for
   karaoke/word-pop animations. Verify word timings survive the swap;
   if they don't, stop and report rather than silently degrading
   subtitles to segment-level.
2. **Download:** `download_video()` fetches `bv*+ba/b` (full video)
   before audio is extracted, but transcription only needs audio.
   Fetch audio-only (`-f ba`) first, start transcription, and pull the
   full video in parallel — or at minimum cap the video format to what
   the 1080×1920 render actually needs instead of "best available".
3. **Normalization:** confirm `normalize_video()` short-circuits when
   the source isn't AV1. If it re-encodes unconditionally, that's a
   large, pure waste.

Don't parallelize by spawning more workers — the loop's
`FOR UPDATE SKIP LOCKED` claim pattern assumes single-item claims and
that's not what's slow here.

---

## Task 5 — Cancel a running job

`'cancelled'` is already a known status (`main.py` ~line 580,
`index.html` `TERMINAL` / `stageLabel` / `badgeClass`) but nothing can
set it and there's no button.

- Add `POST /api/jobs/{job_id}/cancel` in `main.py`: set the job to
  `cancelled` and any of its non-terminal candidates too.
- The worker must actually stop. Long stages (`yt-dlp`, `ffmpeg`,
  Whisper) run inside `run_command()`/blocking calls, so cancellation
  needs a cooperative check: between stages in
  `process_analysis_job()` (and in the candidate/Submagic task loops),
  re-read the job/candidate status and bail out early if it's
  `cancelled`. For the long subprocesses, track the `Popen` handle so
  it can be terminated; if that turns out to be invasive, implement
  between-stage cancellation only and say so in the commit body —
  don't fake it.
- Frontend: a Cancel button on running jobs (Import tab job cards and
  the queue detail view) with a confirm dialog. On success it should
  stop the poller for that job.
- Cancelled jobs must not be re-claimed by
  `claim_analysis_job()` / `claim_candidate_task()` /
  `claim_submagic_task()` — check their WHERE clauses.

---

## Task 6 — Optional subtitle-free output

Let the user turn burned-in subtitles **off** for a render, as a
normal option — separate from Task 3, which only fixed the Submagic
double-caption case. Use cases: the clip goes to an editor who wants
a clean plate, or the platform's own auto-captions are preferred.

**Anchor:** `render_vertical()` in `worker.py` — `subtitle_path` is a
**required** positional parameter (~line 2873) and the `subtitles=`
filter is appended unconditionally (~line 3024). Passing `None` today
would produce a broken filter graph, so this needs a real change, not
just a call-site tweak.

- Make `subtitle_path` optional (`subtitle_path=None`) and skip the
  subtitles filter entirely when it's falsy. Make sure `last`/label
  chaining in the filter graph still links up correctly with that
  stage removed — that's the part most likely to break.
- Add `jobs.burn_subtitles BOOLEAN DEFAULT TRUE` so existing jobs and
  all current behavior are unchanged. When false, `create_preview()`
  and `render_final_candidate()` skip `make_ass()` altogether (don't
  generate an unused `.ass` file) and pass no subtitle path.
- Expose it as a checkbox in the edit panel — "Burn subtitles into
  video", checked by default — committed through `applyEdits()` like
  every other edit, so the preview regenerates without it.
- Reuse Task 3's clean-plate render if that's already producing the
  identical no-subs/no-watermark output; don't create a third code
  path that composes the same thing. Note in the commit body which
  way you went.

**Subtitle edits stay available.** Turning burn-in off must not wipe
`subtitle_override` or the style/animation settings — the user may
flip it back on. It only changes what gets rendered.

**Acceptance:** unchecking the box and hitting Apply produces a
preview and final render with no captions; re-checking restores them
with the previously chosen style/font/animation intact.

---

## Task 7 — UI/UX pass

Scope this to polish, **no behavior changes**, and do it last so it
sits on top of the new controls from tasks 1–6.

- Motion: 100–200ms for in-panel feedback (toggles, thumbnail pick,
  button states), 300–500ms for larger transitions (edit drawer open,
  candidate switch). Per Apple HIG; animation should communicate what
  changed, not decorate.
- Add a `@media (prefers-reduced-motion: reduce)` block that disables
  the caption-preview animation loop and drawer transitions.
- The edit drawer has grown a lot (subtitle text + style/font/size/
  animation + thumbnail + version history + Submagic + watermark +
  burn-in toggle).
  Group it so the primary path (edit text → apply) is obvious and the
  rest is progressively disclosed. Don't hide Apply changes.
- Make loading/disabled states consistent — several buttons currently
  swap their own label text ad hoc.
- Frosted-glass treatment (`backdrop-filter: blur()`) on the edit
  drawer surface and the sticky action row only, not on the video
  preview (that needs to stay flat and high-contrast).

Keep everything keyboard-reachable; the existing `data-*` delegation
pattern already handles Enter/Space on the choice grids — match it for
anything new.
