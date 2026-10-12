
## Update after QA a156a53 (trim not applied on an ordinary compressed clip)
The trim stacked a gain pass on an already limited AAC file: it overshot the peak (dropped) or lost loudness.
Now up to two trims, stopping once within ±0.5 LU: (1) redo the normalising pass from the ORIGINAL with the
target offset by the measured error, (2) a gain pass on the result; each kept only if closer and the peak is no
worse. Throwaway worker container, real downloads, compression on: 6 of 7 land -14.0..-14.4 (before: two at
-14.6); the clipped source stays -15.0.

## Owner decision 2026-10-12: per-clip "Loud & punchy" (option 3) + trim logging
- Every trim decision is logged ("Loudness trim …": measured, what was tried, result, accepted / rejected + why).
  Lane C's clip: the gain try reached -15.2 but its peak (-0.8 dBTP) broke the ceiling; the retarget wasn't closer.
- `edit_spec.audio.loud` (Audio tab switch, default off; Gaming Hype turns it on in E5): `retention.punch_filter`
  pre-chain (level to -20 LUFS, 4:1 fast compressor +6 dB, limiter at -6 dBFS ≈ up to 6 dB of peak reduction) into
  a PCM intermediate, then the normal pass. The ENCODED file is re-measured; above -1 dBTP it is re-limited
  (up to twice, logged "Loudness peak guard"). Off = the old chain; an undershoot keeps the existing chip.
- Verified (throwaway container, compression on, 128k + 96k): Lane C's clip window -14.2 / -1.1 (was -15.4), the
  clipped source -14.0 / -1.3 (was -15.0), two others -14.0..-14.3, all ≤ -1.0 dBTP. Staging final of lane-b-e1 clip
  d35c617d: -14.0 LUFS / -1.2 dBTP (independent ebur128 on the final file).
