# 163 · P4 task 5 — Effects + Audio tabs live (lane B)

- Editor page tabs Effects and Audio are live (Watermark/Export still "later"). Each control saves at once (debounced
  PUT, flushed before Render preview); tab switch slides the panel (reduced motion: none).
- Effects: punch-in switch + intensity slider (existing `edit_spec.zoom`, `PUT …/editor/zoom`); progress bar
  on/off + 4 colours → `edit_spec.progress = {on, color}` (`normalize_progress`, `PUT …/editor/progress`). The
  preview shows a live CSS bar only while there are unrendered changes.
- Render: the bar is ASS drawn into the caption file (`render_steps.add_progress_bar`, after the hook card, own
  `<cid>.title.ass` when captions are off): a track + one `\fscx` fill per KEPT segment, so it runs 0→100 % over
  the cut output without jumps. Height 0.6 % of the frame, top edge.
- Audio: Remove silences = the suggested pauses (≥ 0.6 s, padded) added to / removed from `cuts.removed`, ranges
  remembered in `edit_spec.audio.silence_ranges` so turning it off restores only those. Light compression
  (`acompressor` 3:1 at −20 dB, soft knee) runs in `apply_cuts` (same graph as the cuts, or an audio-only pass
  with the video stream-copied) → before loudnorm, which stays last. Loudness is read-only (−14 LUFS / −1 dBTP).
- `PUT …/editor/audio` = `{compress, silence_trim, silence_ranges}` (owner-scoped like the other editor routes).
- Tests: tests/test_effects.py (spec, piecewise bar through cuts, compression graph), editor.spec.js Effects/Audio.
- Drawer: once merged, the old drawer's Effects and Audio tabs can go (their controls live here now).
