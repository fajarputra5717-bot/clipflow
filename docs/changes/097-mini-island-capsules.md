# 097 · Card-level progress as island-style capsules (P0, Lane C) · index.html, CLAUDE.md

**Rule (CLAUDE.md, verbatim):** Import job-card bars and Publish queue row progress become small island-style
capsules (same shape/colours/motion); the island stays the only global progress indicator.

**Now.** `miniIslandHtml()` + `patchMiniIsland(el, p, status, label)` render `.mini-island`: black capsule
(both themes, like `#island`), 16 px ring (`#0a84ff` fill on a white 18 % track; green ready, red failed),
stage label, tabular %. The ring's `stroke-dashoffset` glides 2200 ms linear like the island's (spans one
poll); only `.is-running` animates, queued/idle capsules are static; reduced motion → no transition.
- Import job cards: patched in place by `patchJobCard()` (keyed cards, no innerHTML re-render); hidden when done.
- Publish rows (`renderQueueJob`): `miniIslandStatic()` in place of the old bar while not done; the separate
  progress-message line is gone (the capsule carries the message).
- Removed: `miniProgressBar()`, `.mini-bar*` CSS, the bar sheen keyframes.

**Verified** headless (light + dark): running import (42 %, "Transcribing audio"), queued import (static, 0 %),
running Publish row (63 %, "Rendering approved clip"); aria-label "stage, n%"; single-card render matches the
pre-change card layout apart from the capsule.
