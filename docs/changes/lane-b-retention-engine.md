# Retention engine (lane B, task 1) — number assigned by Lane A at merge

New `shared/retention.py`: pure builders (argv lists / filter strings) for three effects; no
subprocess, DB or settings reads. Worker integration is a later task.

- **Silence trim:** `silence_detect_cmd` → `parse_silencedetect` → `plan_keep_segments(duration,
  silences, words=, forced_cuts=, min_gap=, pad=, fps=, window=)` → `silence_trim_graph(keep)`
  (split + trim/atrim + concat, 8 ms seam fades). Silence cuts never overlap a word span (+`WORD_PAD`);
  only `forced_cuts` (user-removed fillers) remove words. Boundaries are snapped to the frame grid so
  audio and video come out the same length (smoke: 7.400 / 7.400 s).
- **Word timings:** `TimeMap` + `remap_words()` / `remap_times()` re-time Whisper words and markers
  (zoom, hook, SFX) onto the cut timeline with the *same* keep segments: captions/karaoke never drift.
- **Loudnorm:** `loudnorm_measure_cmd` → `parse_loudnorm` (None = silent/garbage → limiter only) →
  `loudnorm_filter` / `loudnorm_apply_cmd`: linear two-pass to −14 LUFS, then `alimiter` at loudnorm's
  192 kHz (≈ true-peak, −1 dBTP), resample to 48 kHz. Must stay last in the audio chain (after SFX).
  The trailing `aformat=channel_layouts=mono|stereo` is required on ffmpeg 5.1 (else "Cannot select
  channel layout", mono AND stereo).
- **Punch-in zoom:** `plan_zoom_windows(markers, duration)` (output timeline; overlapping windows merge
  into one hold) → `zoom_filter(windows)`: per-frame `scale` with a smoothstep 1.0→1.15→1.0 expression,
  then a fixed 1080×1920 crop. Not zoompan (integer x/y jitter).
- `trim_zoom_cmd` = trim then zoom in one encode (worker encode args); loudnorm measures the result.

Tests: `tests/test_retention.py` (stdlib unittest, 17) and `scripts/retention_smoke.py` (real ffmpeg on
a synthetic clip in a throwaway worker-image container, 2 threads): all pass, −14.04 LUFS after pass 2.
Suggested CLAUDE.md invariant (Lane A to add): "Cuts change the timeline: re-time words/markers with
`retention.TimeMap` built from the same keep segments; loudnorm + limiter always last."
