# QA review · c957031 · 083 caption override only for real edits, word-aligned re-timing (claims QA #1, #3)

Reviewer: Lane C · 2026-10-02 · reviewed against main @ c957031 (deployed worker confirmed to contain it)

Invariants checked: `thumbnail_locked` untouched · `update_candidate` used for the new fields · no
schema change · frontend: Apply still via `api()`/`setBusy`, no new listeners · `create_preview()`
computes `transcript_text` from the extracted segments *before* `apply_subtitle_override()` (so
`subtitle_text` stays the transcript, `data-transcript` in the textarea is correct) · version restore of
a pre-083 snapshot (override == transcript) is now harmless: the aligner maps identical lines back to
their segments with words.

## Re-check of the claimed fixes

- **#1 karaoke: FIXED.** Lane A's post-fix finals 8b974b8e (no edit) and 93ae8661 (line 3 edited,
  + "BANGET") show the two-colour `\kf` sweep mid-line, word by word, including the edited line and its
  inserted word; word spacing correct (`frames/recheck-083/*-karaoke.jpg`). QA's own final render of the
  untouched ccc2a5b1 via the normal approve path: see "Independent render" below.
- **#3 stored segments: FIXED for the preview path.** All 3 finals now have per-line `words` and real
  (non-even) timings in `subtitle_segments`.

## Findings (most severe first)

1. **Low · `subtitle_segments` can still go stale.** `render_final_candidate()` (`worker/worker.py:4844`)
   never writes `subtitle_segments`; only `create_preview()` does. If the override changes without a
   preview (version restore → Final render, or a direct DB edit, as for 93ae8661 today) the stored
   segments lag the burned captions. Live example: 93ae8661 line 3 stored without "BANGET", burned with it.
2. **Low · overlap trim can leave words past the line end.** After sorting, `prev["end"]` is clipped to
   `nxt["start"]` but `prev`'s words keep their times; make_ass then emits `\kf` longer than the line, so
   the last word's fill is cut. Only with reordered/duplicated edited lines.
3. **Info** · the `\kf` block now carries the leading space with the word, so the space fills with its word
   (cosmetic, matches libass karaoke conventions).
4. **Process** · Apply payload change is user-visible, badge not bumped (still v2.1116).

## Not verified
- Non-karaoke word animations (word_pop / bounce / typewriter) with edited lines (different make_ass branch).
- Edits that change the line count (merge/split lines) on a real clip.
- Description/title paths that read `subtitle_override ?? subtitle_text` elsewhere (only 2 frontend
  sites were changed; backend `fix_subtitle_ai` reads both columns and was not re-checked).

## Independent render: PASS
QA re-rendered the untouched ccc2a5b1 via `POST .../approve` (queue idle, 10:16). Mid-line frames at
2.6 / 4.0 / 4.6 s show the sweep advancing word by word ("LOLOS" → "KOK JADI" → "KOK JADI LAMBAT"):
`frames/recheck-083/ccc2a5b1-karaoke.jpg`. QA #1 confirmed fixed on 3/3 finals.
