# 100 · Loudness verification acts: one corrective pass, then a chip (pre-P1 #2, QA Medium + Low #6) · worker.py

**Before.** 086/091 measured finals with ebur128 but only logged it: two earlier finals came out −15.8 LUFS
and +2.3 dBTP with no chip; previews (96k, no re-measure) reached +0.1 dBTP.

**Now.** `normalize_loudness()` re-measures EVERY output (finals and previews) with ebur128
(`_loudnorm_pass()`). `_loudness_ok()` = within 1 LU of −14 LUFS and true peak ≤ −1.0 dBTP. If not:
one corrective pass on that output: loudnorm re-measure + apply with the limiter's codec headroom raised by
the measured overshoot + 0.3 dB (AAC overshoot, worst at 96k), then ebur128 again. Still off → the result is
kept and the `loudness` chip says so with the numbers ("Loudness still off after a corrective pass (… LUFS /
… dBTP; target −14 LUFS, ≤ −1 dBTP)…"). OK → chip cleared. Errors keep the un-normalised file + chip (091).
The log line names the corrective pass: `… -> -14.1 LUFS / -1.6 dBTP (pass 1 -14.2 LUFS / -0.2 dBTP;
corrective pass, headroom 1.6 dB)`.

**Verified** in the worker (35 s cuts at 96k, as previews): +12 dB boosted source → pass 1 −14.2 / −0.2 dBTP
→ corrected −14.1 / −1.6, no chip; plain source → pass 1 −14.0 / +0.4 → −14.5 / −2.1, no chip; both passes
forced off → file kept, chip with the numbers; no temp files left. Real preview render (9c5f3050): `9c5f3050-23c2-4a7a-bc19-51961b421155.mp4 -25.8 LUFS / -5.7 dBTP -> -14.8 LUFS / -1.1 dBTP (pass 1 -14.7 LUFS / -0.7 dBTP; corrective pass, headroom 1.1 dB)`, chip cleared.
