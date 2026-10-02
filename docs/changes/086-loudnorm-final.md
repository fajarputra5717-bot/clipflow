# 086 · Loudness normalisation in the final render (QA #2) · worker.py

**Before.** No loudness step: finals ranged −28.6…−11.8 LUFS, one at +0.9 dBTP (QA clips #2).

**Now.** `render_final_candidate()` → `normalize_loudness(output_path, duration)` after the encode, as the
last audio step (085's builders): ffprobe audio check (none → skip + log) → `ensure_disk_space("loudness")`
→ loudnorm pass 1 (measure) → pass 2 linear loudnorm −14 LUFS + `alimiter` at TP −1 dBTP − 0.5 dB codec
headroom, 48 kHz, AAC 128k, **video stream-copied** → ebur128 verification → atomic replace. All steps via
`run_command` with the render watchdog timeout (cancellable). Log line:
`Loudness: <id>.mp4 <in LUFS/dBTP> -> <out LUFS/dBTP>`. Progress shows "Normalising loudness" at 90 %.
Previews are not normalised (cheap iteration); silence trim and zoom from 085 stay unwired.

**Verified** on the stack (re-rendered finals): 93ae8661 −11.9 LUFS / +0.8 dBTP → −13.9 / −1.5;
8b974b8e −27.2 / −11.3 → −14.3 / −1.3. Independent ebur128 run agrees on I; audio/video durations still
match (35.40/35.41, 36.80/36.80); no temp files left.
