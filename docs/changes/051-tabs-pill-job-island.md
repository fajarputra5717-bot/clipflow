# 051 — Tabs pill motion + separate job island (R-13)
Date: 2026-09-29 · Commit: see `git log --grep R-13` · Files: frontend/html/index.html, docs/changes/ui-audit.md · UI v2.1103

## What changed
- **Audit first (QA T1):** `docs/changes/ui-audit.md` covers affordances, every transition (parsed from the CSS),
  badge colours with measured contrast, state coverage and focus. Findings owned by later QA tasks (T4–T7:
  thumbnails, chevrons, badges, a11y) are listed there, not fixed here.
- **Tabs pill (QA T2):** the pill has a constant layout size. Tabs are equal-width grid columns, so the indicator only
  `translateX`es. Docking = `transform: scale(.88)` plus an opacity cross-fade between two shadow layers
  (`::before` bar, `::after` docked). No width/padding/gap/radius/font-size transitions remain on the scroll path.
  Dock takes 420 ms ease-out and undock 320 ms with a small overshoot. `will-change: transform` is set only while
  moving (`.is-moving`, removed on `transitionend`).
- **One scroll owner:** `initTopbarDock()` is a rAF-throttled passive scroll handler with hysteresis (dock above 64 px,
  undock below 48 px). It replaces the `#headerSentinel` IntersectionObserver and the `.tabs` `transitionend`
  indicator re-measure (the two handlers that conflicted). The sentinel element is removed.
- **Job island (QA T3):** its own fixed-width capsule (≤240 px), absolutely positioned at the row's leading edge. Its
  width is capped by `50cqi - tabs half-width - 16px`, so it can never reach the centered tabs. When the topbar is
  ≤600 px wide (container query) it drops below the tabs, centered. It shows the lead task's title (ellipsis), a
  plain-language stage, the %, and `+N` for other tasks. The progress bar is `scaleX`. Enter/exit is opacity + transform
  only; all JS width measurement/FLIP code is deleted. It gets `aria-expanded`/`aria-controls`, a descriptive
  `aria-label`, and a `role=status` live region announced on stage changes and 25 % steps.
- This **reverses** the old v2.x merge of tabs and island into one cluster that re-centered as the island grew
  (the original `016-dynamic-island-header.md`, lost with the VM). Tabs are navigation and always present; job status
  is transient. Sharing one row that re-centers made both jump whenever a job started or finished.

## What I verified (headless Chromium 153 via Playwright, :8081 preview)
- Hysteresis at 1280/800/390: scrollY 0,56,70,56,50,40,0 → `- - D D D - -`.
- The tabs' `offsetWidth` stays constant through a dock (only the visual width scales 166→146 px). Layout count during a
  600 ms undock is 1 (the class toggle), not one per frame.
- Mid-motion frames (the CSS transitions were paused and seeked to 0/40/80/120/180/260/420 ms) were inspected: a
  uniform scale, no child reflow, and the indicator stays attached.
- Island with a long title plus 2 tasks at 1280, 1280 with the sidebar collapsed (dark), 800 and 390: never
  overlaps the tabs pill, whether docked or not. The bar reaches 60–77 %, click opens the overlay, and it hides after
  the tasks clear. No console errors.

## What I did NOT verify
Subjective feel on real hardware (Safari especially, where backdrop-filter plus transform costs more), a real
screen reader reading the live region, and a long-running real job end to end (fake candidate tasks were injected via
`setCandidateActiveTask`).
