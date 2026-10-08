# 177 · QA Lows after 3d85c4d (lane-b)

- Low 3: `languages.filler_spans` skips spans shorter than 80 ms (`FILLER_MIN_SPAN`), the cuts endpoint drops them.
- Low 2: `normalize_loudness()` adds a trim pass: when the measured result is > 0.5 LU from -14, a plain gain
  (`retention.gain_filter`, same limiter chain) by the measured error is applied; kept only if closer to the target and
  the true peak is no worse. Tested in a throwaway worker container on real downloads with compression on: 4 of 5
  ordinary clips land -13.8..-14.1. A heavily clipped game-audio source (input +5 dBTP) still lands ~-15.1 /
  -0.5 dBTP with or without compression: AAC overshoots there, so the peak ceiling wins over loudness (chip rules unchanged: > 1 LU).
