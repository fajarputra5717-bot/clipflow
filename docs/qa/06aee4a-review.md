# touch-margin 06aee4a (225) — Editor touch targets at 390 / 360 px, served copy vs main d775bdb

Served myself (throwaway nginx on the staging network, `git archive origin/touch-margin` v3.225 and main d775bdb as baseline; removed afterwards). Hit areas measured as the real extent where `elementFromPoint` returns the control, scanned outward in 0.25 px steps with the control scrolled to y ≈ 620 (clear of the sticky player and the dock). This corrects my earlier probe (22 px from the centre sat on the 44 px boundary and under the sticky player; Lane A was right that those controls had 44 px areas).

| control (390 px, Editor) | main d775bdb | touch-margin 06aee4a |
|---|---|---|
| switches (Hook, Burn, Effects, Audio tabs: 11 measured) | 44.5 × 44.5 | **44.5 × 46.5** ✓ |
| keyword colour swatches (5) | 37.8 × 40.5 (centres 38 px apart, gap 12) | **37.8 × 42.5 (centres still 38 px, gap still 12)** ✗ |
| trim handles (Clip start / end) | not measurable by my probe | not measurable (see below) |

- **Switches: fixed.** 44 px wide and 46.5 px tall at 390 and 360, in all tabs; no horizontal overflow at either width.
- **Swatches: not effective yet.** The new `.ed-swatches{gap:20px}` (index.html:1790, inside the phone media block) is overridden by `.ed-swatches{display:flex;gap:12px;…}` in `frontend/html/editor/editor.css:191`, which loads after it with the same specificity: the live gap stays 12 px (spacing 38 px). Neighbouring 44 px areas therefore overlap and each swatch gets only 37.8 px of width; its height is 42.5 (not 46) because the keyword chips right below take taps on the bottom ~3.5 px. Fix: raise the specificity or move the phone rule into editor.css (e.g. `.ed-page .ed-swatches{gap:20px}` in the phone media block).
- **Trim handles:** they sit in the horizontally scrolled timeline (3,600 px wide, clipped to a 72 px box at the default split); my probe could not bring them under a finger-size test; Lane A's numbers (18 + 2×13 = 44 wide) were not re-measured by me. Low confidence.
- Their new touch.spec probe (tap 21 px from the centre) passes for switches; for swatches 21 px lands on the neighbour at a 38 px spacing, so it would only pass if the test skips them or the gap rule worked in their environment (a different CSS load order, as in a bundled test server).

Merge: OK for 06aee4a as an improvement (switches fixed, no overflow, nothing worse than main), but the swatch half of the fix is not live: don't claim ≥ 44 px for the colour swatches until the gap override is fixed.

## Addendum: f1d64a1 (swatches fixed for real) — closed
Re-measured on a served copy of f1d64a1 (same method). **Swatches: 44.5 × 46.5 px** each, centres 46 px apart (gap 20) at 390 and 360 (at 360 they wrap to two rows, no overflow); computed `column-gap` 20 px and padding 10 px on the phone row, 12 px / 0 on 768, 1280 and 1440 (desktop unchanged). **Switches: 44.5 × 46.5** (Hook, Burn, Effects, Audio tabs). No horizontal overflow at 360, 390, 768, 1280, 1440; 0 page errors. Agreed on the cause: the `inset` counts from the padding box inside the swatch's 2 px border, plus editor.css:191's gap override.
Still open: the trim handles (Clip start / end, 18 px wide + 13 px areas, clipped by `#edTlInner`): not fixed, handed to Lane B; I could not measure them either.

Merge: OK for f1d64a1 (swatches + switches done; trim handles open for Lane B).
