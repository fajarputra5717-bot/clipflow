# 085 · Retention engine (lane B): silence trim + word re-timing, loudnorm, punch-in zoom — builders only · shared/retention.py, tests, scripts

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

## 1b — real clips (2026-10-02)

`scripts/retention_real_check.py` on 3 finals (copies; outputs in /tmp only), Whisper medium on
2 CPUs. Clip 3 was boosted +12 dB first (true peak +0.4) to force the limiter.

| clip | before → after | cuts | LUFS after | TP after | audio spot checks (offset, corr) |
|---|---|---|---|---|---|
| 93ae8661 (TP +0.9 as shipped) | 35.40 → 35.41 s | 0 | −13.9 | −1.0 | 1/1/1 ms, ≥0.91 |
| ccc2a5b1 | 46.00 → 46.02 s | 0 | −14.1 | −1.3 | 1/1/1 ms, ≥0.98 |
| 8b974b8e +12 dB | 36.80 → 32.11 s | 3 (4.7 s) | −14.2 | −1.0 | 1/1/1 ms (2 right after cuts), ≥0.99 |

Fixed on the way (engine):
- AAC overshoot: a −1.0 limiter came out at −0.7/−0.8 dBTP after encoding → ceiling now
  `CODEC_HEADROOM_DB` (0.5) below TP. Clip 3 without the limiter: −0.5 dBTP encoded.
- loudnorm's own JSON re-measure read −13.3 where ebur128 read −14.1 → `ebur128_measure_cmd` /
  `parse_ebur128` for verification.
- Zero-length Whisper words were dropped (11/80 on one clip) → kept with `MIN_WORD_DUR`.
- Finals carry a music/game bed: the −35 dB default found 0 cuts on all 3 → `relative_noise_db()`
  (LUFS − 14, clamped −50..−25) as an option; clips 1–2 still have no pause ≥ 0.5 s.
Spot checks cross-correlate the word's source audio with the output at the TimeMap-predicted time
(the constant 1 ms is AAC priming); Whisper-vs-Whisper deltas are only a coarse cross-check.
