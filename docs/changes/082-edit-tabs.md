# 082 · Edit drawer → tabs (Captions, Effects, Audio, Watermark, Export) · index.html

**Before.** The candidate edit drawer was one long stack: Subtitle section, then `<details>` for
Description, Thumbnail and Watermark.

**Now.** Editor redesign commit 1 of 5 (spec: `flow-preview.html` step 5).
- Segmented tablist `.edit-tabs` (ARIA tabs, arrow keys / Home / End). Thumb is placed by index
  (`--i` × column width) so it works while the drawer is still hidden; panels slide in (`in-l`/`in-r`),
  skipped under reduced motion.
- Captions: subtitle text, style/font/size/animation, live preview. Effects / Audio: "Coming soon"
  (wired in once Lane B's retention engine lands). Watermark: the R-05 per-job size/opacity controls.
  Export: burn-in toggle (moved from Captions), Description, Thumbnail. Version history + the sticky
  Apply / Final render row stay below the panels.
- Active tab per candidate in `editTab[cid]` (survives polling re-renders). Inactive panels stay in the
  DOM (`hidden`), so `applyEdits()` still reads every input unchanged.
- New tokens `--fill` / `--seg-thumb` in both theme blocks.

**Verified** headless at 1280 light and 390 dark: click + arrow-key switching, focus follows, all Apply
inputs present, screenshots of each panel.
