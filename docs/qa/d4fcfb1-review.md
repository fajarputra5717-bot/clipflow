# lane-b d4fcfb1 — smooth playhead + drag-to-scrub (staging :8080)

Measured with CDP Performance metrics + rAF frame times + longtask observer on my lane-c-a clip (headless Chromium, software compositing), 1280×800 and 390×844.

| | 1280×800 | 390×844 |
|---|---|---|
| 3 s playback: layouts / layout time / style recalcs | 30 / 7 ms / 188 | 30 / 6 ms / 192 |
| playback frames: p95 / worst / > 34 ms / long tasks | 17 / 17 ms / 0 / none | 17 / 17 ms / 0 / none |
| 2 s waveform drag: scrub | 3.83 s → 6.80 s (mouse path 60 → 680 px = 0.6 → 6.8 s at 100 px/s: exact) | 3.87 → 6.36 s (path clipped by the narrower timeline) |
| drag: layouts / layout time | 62 / 15 ms | 30 / 6 ms |
| drag frames: p95 / worst / > 34 ms / long tasks | 17 / 17 / 0 / none | 17 / 17 / 0 / none |

- Painters: playhead `transform: translateX(383px)`, scrub fill `transform: scaleX(0.113)` (transform only). Lane B's claim (layouts 378 → 32 over 3 s) reproduces: 30 here.
- Drag on the waveform in Seek mode scrubs and the playhead follows (`translateX(680px)`); the same drag in Cut mode (key C) does NOT scrub; moving after the button is released does not scrub (no stuck drag). 0 page errors.

## Findings
None.

## Not verified
Drag starting on a chip, trim handle or marker (not scrubbing); touch dragging on a real phone (mine was mouse events at 390); real 60 fps on slow hardware/Safari; `pointercancel`.

Merge: OK
