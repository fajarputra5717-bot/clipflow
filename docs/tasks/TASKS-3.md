# ClipFlow — phase 3: make native output beat Submagic

Goal: the native renderer becomes good enough that Submagic is optional.
The gap right now is **not** the pipeline — it's typography, keyword
emphasis, and preset richness.

Read `CLAUDE.md` and `docs/changes/INDEX.md` first. Grep for function
names; don't trust remembered line numbers. Same ground rules as
TASKS.md: one commit per task, `docs/changes/NNN-<slug>.md` + INDEX
line, schema via `ensure_schema()`, settings via `DEFAULT_SETTINGS`,
compile checks, honest "what I did NOT verify" notes.

---

## Task 0 — Reality check on the renderer (do this first, it decides everything)

Before building anything below, **spike-test what libass can actually
do** and write the findings into the change-log entry. This decides
whether tasks 1–5 are ASS tweaks or need a different render path.

Test, with real ffmpeg output you actually look at:

1. **Per-word colour inside one line** — `{\c&HXXXXXX&}` mid-line.
   Needed for keyword highlighting (task 2). Should work; confirm it
   survives alongside `\kf` karaoke timing.
2. **Rounded box backgrounds.** `BorderStyle=3` gives a box but square
   corners, sized to the line, no padding control. Submagic's look is
   a rounded, padded white box per line. Check whether ASS drawing
   commands (`\p1` with a rounded path, drawn as a separate event
   behind the text) are viable, or whether that's too fragile.
3. **Colour emoji.** libass support for CBDT/COLR emoji fonts is
   historically unreliable — it often renders monochrome or as tofu.
   Test with Noto Color Emoji before promising task 4.
4. **Per-word independent animation** — separate `\t` transforms on
   individual words within a line, not just whole-line.

**If ASS can't do rounded boxes or emoji acceptably**, the fallback is
to render caption frames as transparent PNGs (Pillow — already a
dependency, used by the thumbnail uploader) and overlay them with
ffmpeg on a timeline. That buys full typographic control at the cost
of a much heavier render step. **Don't pick this silently** — report
the trade-off and let me decide. My default preference: stay in ASS
for anything ASS does well, and only reach for PNG overlay if a
specific, high-value effect genuinely requires it.

---

## Task 1 — Real display fonts (biggest visual win per hour of work)

This is why native output looks generic. The current font list is
`Liberation Sans`, `Noto Sans`, `DejaVu Sans` — Linux system defaults.
Submagic ships display faces built for short-form.

- Bundle open-licensed display fonts in the worker image. **SIL OFL
  only** — verify each licence before adding, don't assume:
  Anton, Bebas Neue, Montserrat (Bold/ExtraBold/Black), Poppins
  (Bold/ExtraBold), Oswald, Inter (Bold/Black), Archivo Black.
  These cover the actual short-form caption look.
- Add them to the Dockerfile (`/usr/share/fonts/truetype/clipflow/`),
  run `fc-cache`, and confirm libass resolves them by the exact family
  name ASS expects — a wrong family name silently falls back to a
  default, which is the classic failure here. Verify by rendering and
  *looking*, not by the absence of an error.
- Update `SUBTITLE_FONTS` in `index.html` and make the font dropdown
  render each option **in its own typeface** so the user picks by
  appearance.
- Ship the licence files alongside the fonts in the image.

---

## Task 2 — Keyword highlighting (the single biggest look difference)

Submagic colours the *important* word in a line differently — red/
yellow against white. That one detail is most of why their output
reads as "professionally edited." Native currently colours purely by
karaoke timing, which is a different thing.

- Pick emphasis words per caption line. Two approaches; do the cheap
  one first and measure:
  - **Heuristic:** longest non-stopword, or the word with peak audio
    RMS in its time window (the audio is already extracted). Free,
    no API call, no latency.
  - **AI:** ask Gemini for emphasis-word indices alongside the
    existing hook analysis. Better, but adds cost/latency to every
    clip. Only do this if the heuristic visibly underperforms.
- Render via inline `{\c}` colour overrides on those words in
  `make_ass()`. Must compose correctly with existing `\kf` karaoke
  timing and every animation mode — test all six.
- Expose highlight colour in the style preset, not hardcoded.
- **Indonesian stopword list**, not English — the transcripts are
  Indonesian (`WHISPER_LANGUAGE=id`). An English stoplist will
  highlight "yang" and "untuk" and look broken.

---

## Task 3 — Preset system / brand kit

Style, font, size, animation, highlight colour, and watermark are
currently set per job with no way to save a combination. Submagic's
templates are exactly this.

- `caption_presets` table: name + full style JSON (style, font, size,
  animation, highlight colour, position, box on/off, margins).
- Ship 6–8 built-in presets tuned to look genuinely distinct — a
  Hormozi-style big-word, a clean minimal, a boxed-caption look, a
  neon/gaming look. Name them memorably; creators pick by vibe.
- Save-current-as-preset, apply-preset-to-candidate, and
  apply-preset-to-all-candidates-in-job.
- A default preset setting so new jobs start from the user's house
  style instead of the hardcoded defaults.
- Preset picker shows a **rendered thumbnail preview** of each, not
  just a name. Reuse the existing live CSS caption preview — it
  already mirrors the ASS styles.

---

## Task 4 — Emoji in captions (only if task 0 cleared it)

Submagic injects contextual emoji. Gated on the task 0 finding.

- If libass handles colour emoji: pick 0–2 emoji per line via Gemini
  (batch with the emphasis-word call from task 2 — one API round trip,
  not two), make it a per-preset toggle defaulting **off**.
- If libass can't: say so plainly in the change log and skip it.
  Don't ship monochrome tofu boxes as "emoji support."

---

## Task 5 — Caption layout modes

Currently captions are one line at a fixed position. Short-form uses
several distinct layouts:

- **Word-by-word** (one huge word at a time — already partly there via
  the `chunk` animation mode).
- **Two/three-line block** with the active line highlighted.
- **Boxed** — padded background per line (depends on task 0's finding).
- Vertical position as a preset property, respecting the
  per-platform safe zones from phase 2 task 6.

Keep the existing `make_ass()` structure — this is more modes in the
same dispatcher, not a rewrite.

---

## Task 6 — Rich caption editing UI

The current editor is one textarea for the whole clip's text. To beat
a paid tool, the editing has to be better, not just the render.

- **Word-level timeline editor:** show words on a scrubber with their
  Whisper timings; let the user nudge a word's start/end, split or
  merge caption lines, and delete filler words. Word timings already
  exist in `transcript_segments`.
- **Per-word style override** — mark any word as emphasised manually,
  overriding task 2's automatic pick.
- **Click a word to seek** the preview video to that timestamp.
- Keep the existing "Apply changes" commit model — edits stage
  locally, one apply, one re-render. Don't re-render per keystroke.

This is the largest task here. If it's too big for one commit, split
it: read-only word timeline first, then editing on top.

---

## Task 7 — Animation polish

The six animations work but are mechanically simple next to
Submagic's.

- Add easing. Current `\t` transforms are linear; ASS supports an
  accel parameter — a slight overshoot-and-settle reads far more
  "designed" than a linear scale.
- Subtle per-word rotation (±2°) on pop animations for organic feel.
- Shadow/glow pulse synced to the emphasised word from task 2.
- A genuine typewriter with a cursor, if task 0 showed per-word
  independent timing works cleanly.

Don't add animations nobody picked — **fix the feel of the six that
exist** before adding a seventh.

---

## Order and priorities

1. **Task 0** — decides the rest.
2. **Task 1 (fonts)** — highest visual payoff per hour. Do it even if
   you do nothing else on this list.
3. **Task 2 (keyword highlighting)** — the signature Submagic look.
4. **Task 3 (presets)** — makes 1 and 2 reusable instead of fiddly.
5. Then 5, 7, 6, and 4 last.

Tasks 1–3 alone should close most of the perceived gap. Be honest in
the change logs about where native still loses — that's more useful
than claiming parity.
