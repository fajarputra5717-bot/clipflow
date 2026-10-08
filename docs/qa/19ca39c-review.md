# lane-b 9a6c9fd, 9364e01, 2be0487, 19ca39c (HEAD) · Lane C · 2026-10-09
9a6c9fd: source_watch now builds its runner with shared/ytdlp (base_args, wait_turn, one cookies retry, BLOCKED_MESSAGE): closes the 452c7d8 Medium. Still open (not touched): baseline with a failed /streams tab (backlog flood), ids marked seen before the caller creates the job, per-channel (not per-user) state, no file lock. Module is imported nowhere yet, so no runtime effect; fix before wiring.
2be0487: filler_spans skips < 80 ms (FILLER_MIN_SPAN), matches the cuts endpoint: closes Low 3.
19ca39c: loudness trim pass (±6 dB gain, same limiter chain, kept only if closer and peak no worse). Checked on the staging final 0a5548a8 with the same filter chain by hand: -14.8 -> -14.1 LUFS, peak -0.9 (my approximation used limit 0.891; production uses 0.841 so the peak will be lower). Accepted by owner: clipped sources may land ~-15 LUFS with the chip. Note for the record: those clips also end at about -0.5 dBTP, above the -1 ceiling (AAC overshoot); owner accepted the clip, TP not mentioned.
9364e01: review score row wraps (CSS/JS only).
Playwright vs staging at 19ca39c: 185 passed, 5 skipped, 0 failed (187 before; keywords/presets specs were removed with the drawer tabs). Unit tests not run (no pytest on host). Staging worker/backend not restaged with 19ca39c (code read, not rendered).
Merge: OK at 19ca39c.
