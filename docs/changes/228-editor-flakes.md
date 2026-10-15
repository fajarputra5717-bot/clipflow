# 228 — two editor.spec flakes (Lane A, 2026-10-15) — one real bug

- "Timeline keys" was a real bug from 219: opening the Effects tab fetches `/api/sfx` and, on arrival, repainted the
  whole panel, so a control the user had already focused (zoom slider, a picker) lost focus and arrow keys went to the
  player. `loadSfxLib()` now relabels the sound options in place; new editor.spec test with a slow `/api/sfx` (fails on
  the old code).
- "Z toggles zoom mode" pressed Z before the timeline had loaded (the key needs it): the test now waits for a word chip.
Both ran 15× each in parallel with 0 failures (were 1–2 per 12 runs).
