# 214 · Desktop sheet opens without dropped frames (deep audit L9, 2026-10-14)

Opening Settings/Watermarks on desktop dropped frames (Lane C: 8 frames > 34 ms, worst 67 ms at 1280). Measured
(headless 1280, 4 opens each, frames > 34 ms / worst): as shipped 6–9 / 83 ms; without the backdrop's blur 4–5 / 50–83;
without both the backdrop's and the sheet's own `backdrop-filter` 0–1 / 33–50. The full-viewport blur under a scaling,
itself-blurred sheet re-rendered every frame. The sheet is 88 % opaque, so the blur barely showed: ≥ 601 px now has no
backdrop-filter on either (backdrop dims to .34, sheet = `--panel`); phones keep the frosted material (390 was already
clean). After: 0–1 frames > 34 ms, worst 33–50 ms. UI 254 passed.
