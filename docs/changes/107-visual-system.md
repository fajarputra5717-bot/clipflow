# 107 · Visual system (P1 task 0, part b): flow-preview type scale, buttons, panels, inputs app-wide · index.html

One block at the end of the stylesheet (same specificity as the base rules, so it wins; components that set
their own size/colour keep it, e.g. island, capsules, chips, badges, preset/thumbnail cards):
- body 15 px / 1.47, h2 24/700, h3 17 px;
- pill buttons 15 px, no border/shadow; secondary = `--fill` (hover `--fill2`) in both themes; in dark mode
  plain (unclassed, non-`role`) primary buttons use the accent like the mockup (they were grey); tab buttons
  keep the segmented look;
- panels: 24 px padding (16 px ≤ 600 px), `--line` hairline, new `--shadow` token (both themes);
- inputs/selects/textareas: 15 px, 11×14 padding, 12 px radius, `--line2` border, `--ring` focus;
- field labels 13 px muted.
Island untouched.

**Verified:** screenshots Analyze + Editor at 1280 light, 1280 dark, 390 light (a first pass painted the
dark edit tabs blue; fixed by excluding `role` buttons); UI harness 24/24.
