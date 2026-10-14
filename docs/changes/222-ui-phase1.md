# 222 — UI task phase 1 (global): scale, dock, one title, menu, version, one accent, one-line intros

Owner UI task 2026-10-14 (two phases; Lane A = phase 1 + 8 pages of phase 2, Lane B = Review/Editor/Sound effects).
Before/after screenshots: 1280×800, 1440×900, 390×844, light + dark (`tests/ui/specs/phase-shots.spec.js`,
PHASE_SHOTS=<dir>).

1. **Scale ×1.2** (c59929e): tokens.css body 16 px, secondary 14 px, h1 24, h2 19, controls 44 px, chips 28, spacing
   tokens ×1.2, top bar 56 px; 228 hard-coded font sizes in index.html ×1.2 (floor 12 px; island text set by hand to fit
   its capsule). `--sp-4` stays 2 × `--sp-2` (container gap = the top bar's bleed; 38 px made pages 1 px too wide).
   scale.spec: no horizontal overflow at 390×844 and 1280×700 on every page, the menu and Settings.
2. **Dock** (527d96a): 48 px icon buttons (44 phone), 24 px icons; a glider slides under the active step (transform
   only; spring); the step name is a tooltip on hover/keyboard focus; bar → pill on scroll in initToolbar's one
   handler with hysteresis (> 64 px on, < 24 px off): desktop scale(.88) + a cross-fade of two glass layers (only the
   visible one blurs), phones keep 44 px. Liquid glass = translucent fill + backdrop blur/saturate + highlight border;
   solid with `@supports not (backdrop-filter)` and `prefers-reduced-transparency`; no transitions with reduced motion.
   Frames (headless, software rendering, desktop, 3 runs): scroll 16/16/27 slow frames vs main 31/24/27; page switch
   10–11 vs 9; phone 0 (dock.spec, DOCK_FRAMES=1). Real GPUs: Lane C.
3. **Bottom padding** (c9adc74): body = dock height + its offset + 20 px; scale.spec "nothing hides under the dock"
   (long pages) fails on main (Publish at 390), passes here.
4. **One title** (910c56b): the page's own heading; the top bar's #pageContext is gone (and its DOM observer).
5. **Account menu** (5609c9f): Watermarks + Settings out of the markup (top-bar icons; the dark theme's
   `.acct-item{display:flex}` used to override `.acct-narrow{display:none}`); phones (≤ 600 px, no room beside the
   island) get them inserted by `syncNarrowMenu()`; Refresh dropped; version a plain label beside What's new.
6. **Version** (3381b9e): v3.<highest change number>; `scripts/write_version.py` writes it + the latest 5 INDEX
   entries to `frontend/html/version.json` at every merge; tests/test_version.py fails when stale.
7. **One accent** (6850b4d): switches that are on (.ai-switch, editor .ed-switch) and native checkboxes use the accent.
8. **One-line intros** (eff499c, 31baba6): Campaigns, Analyze, Schedule, Auto-import (+ its footer), Track, Pick a
   clip, Publish, Review: one sentence; the rest behind an info button (aria-expanded/controls, 44 px hit area).

Also: sfx.spec mocks serve a real silent WAV (cb414dc; the flaky play check Lane B reported).
