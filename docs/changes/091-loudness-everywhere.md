# 091 · Loudness on every output, never fatal, with a visible warning (P0 items 1–3) · worker.py, main.py, index.html

**Before (086).** Only native finals were normalised; a loudnorm error failed the whole final render; the
Submagic "use as final" path (`apply_watermark_overlay`) and previews skipped it.

**Now.** `normalize_loudness(path, duration, *, candidate_id, verify=True, audio_bitrate)`:
- Same two-pass chain everywhere (−14 LUFS, limiter −1 dBTP minus codec headroom, video stream-copied):
  native finals (`verify=True`, ebur128 check), **Submagic finals** after the watermark overlay (verify), and
  **previews** (`verify=False`, 96k). A single-pass dynamic loudnorm was tried for previews first and measured
  −15.5 LUFS / −0.8 dBTP, so previews use the measured two-pass chain (the measure pass is audio-only, ~1–2 s).
- **Never fails the render.** Any error (disk, ffmpeg, timeout) → the rendered file is kept un-normalised, the
  temp file removed, and `clip_candidates.render_warnings` gets `{code: "loudness", message, at}`; the next
  successful pass clears it. `JobCancelled` still propagates.
- **Disk:** `ensure_disk_space("loudness", need_mb = 2 × file size)`.
- New column `clip_candidates.render_warnings` JSONB (`set_render_warning(cid, code, message|None)`), shown
  as warn-token chips under the clip title (`renderWarningsHtml`). Reused for the campaign watermark check.

**Verified** on the stack: preview re-render of 9c5f3050 → −25.8 LUFS in, −14.7 LUFS out (ebur128);
forced apply failure (patched `run_command`) → returns None, file byte-identical, no temp left, warning set
and shown as a chip in the UI; next successful preview cleared it. Native finals as in 086.
**Not exercised:** the Submagic path end to end (export is billable); it calls the same function after the
overlay. **Known:** preview true peak reads −0.7 dBFS (96k AAC overshoot); finals at 128k stay ≤ −1.2.
