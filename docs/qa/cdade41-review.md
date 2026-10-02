# QA review · cdade41 · 086 loudness normalisation in the final render (claims QA #2)

Reviewer: Lane C · 2026-10-02 · deployed worker confirmed to contain it

Invariants checked: through `run_command` with `render_timeout_seconds` (watchdog + cancel) · `ensure_disk_space`
called · temp file named after the candidate (`<cid>.loudnorm.tmp.mp4`, orphan-sweep safe) and removed in
`finally` · video stream copied (`-c:v copy`), so captions/watermark untouched · runs last in
`render_final_candidate()` (`worker/worker.py:5063`) · no-audio files skipped.

## Re-check: FIXED
| final | before | after (QA ebur128) | target |
|---|---|---|---|
| 93ae8661 (QA render 10:20) | −11.8 LUFS, +0.9 dBTP | **−13.9 LUFS, −1.5 dBTP**, LRA 12.3 | −14 ±1, TP ≤ −1 ✓ |
| 8b974b8e (Lane A render 10:18) | −28.6 LUFS, −11.3 dBTP | **−14.3 LUFS, −1.3 dBTP**, LRA 9.3 | ✓ |
Output: AAC 48 kHz ~130 kb/s, 1080×1920 unchanged, duration +11 ms (AAC priming). Karaoke still sweeps after
the audio pass (`frames/recheck-086/93ae8661-karaoke.jpg`). ccc2a5b1 (−15.5 LUFS) not re-rendered since.

## Findings (most severe first)
1. **Medium · Submagic finals skip loudness.** `apply_watermark_overlay()` (`worker.py:6735`, the
   use-as-final path) never calls `normalize_loudness()`, so a Submagic final keeps Submagic's loudness.
2. **Low · disk guard reserves 0 MB.** `ensure_disk_space("loudness")` passes no `need_mb`, but the step
   writes a full temporary copy of the final (~20 MB per clip).
3. **Low · a loudnorm failure fails the whole final**, though the rendered video was fine; consider keeping
   the un-normalised final with a warning.
4. **Low · previews aren't normalised**, so preview loudness ≠ final loudness (user may misjudge levels).

## Not verified
- Silent / music-only clips (the `SILENT_INPUT_LUFS` branch); clips with no audio stream.
