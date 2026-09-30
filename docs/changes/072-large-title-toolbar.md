# 072 — Toolbar: iOS large title (continuous), bottom tab bar, no tabs pill
Date: 2026-09-29 · Commit: see `git log --grep "072"` · Files: frontend/html/index.html, docs/ui-recordings/072-*.webm, CLAUDE.md · UI v2.1107

## What changed
- **Removed:** the floating tabs pill (`#tabsNav`, indicator, `role=tab` keys), the bar→pill dock
  (`initTopbarDock`, 64/48 hysteresis), the "R" topbar logo chip plus its floating theme toggle and width-measuring
  JS, and the old brand header (logo, "ClipFlow", subtitle). Navigation lives in the sidebar (068), and the brand
  is in the sidebar head.
- **Large-title toolbar** (`#toolbar`, sticky, 52 px): sidebar button · **one** title element `#pageTitle`
  ("Import"/"Publish") · centre slot (the job island, parked until 073) · version chip · refresh.
  - `initToolbar()` is the only scroll driver: rAF-throttled and passive. It maps `scrollY / 48` onto `--p`
    ∈ [0,1] and writes only when the value changes.
  - CSS derives the title from `--p`: `translateY((1-p)·46px) scale(1 - .5p)` from the left edge, so 34 px under the
    bar at the top becomes 17 px inside it. `.toolbar-bg` opacity = `--p`, and it carries the material blur, the
    hairline and a 14 px scroll-edge fade below the bar.
  - Everything is transform or opacity; nothing relayouts on scroll. There is no threshold jump and no snap.
- **View switch while scrolled:** if you're past the title range, the page returns to exactly 48 px (title
  collapsed, section top under the bar). This replaces `freezeUnderHeader`'s dock logic.
- **≤600 px bottom tab bar** (`#tabbar`, material, safe-area aware): Import / Publish / Watermarks / Settings using the
  same `[data-nav]` + `syncNav()`. Current = accent plus a spring icon scale. The body reserves space, and the toast
  sits above it. The version chip is hidden on phones.

## Decisions & trade-offs
- The large title is not suppressed under reduced motion: it follows the user's own scroll 1:1, which is direct
  manipulation rather than an animation (iOS does the same). No time-based motion was added.
- Content under the transparent part of the bar (while p < 1) isn't clickable in that 52 px band. The content starts
  below the spacer, so nothing sits there at rest.

## Verification (headless Chromium, :8081, /api mocked with 14 Publish jobs; light/dark × 1280/800/390)
0 errors. No pill or logo-chip elements remain. Title switches Import ↔ Publish. Scroll sampling at y =
0/12/24/36/48/90 gives `--p` 0/.25/.5/.75/1/1, scale 1/.875/.75/.625/.5/.5, translate 46/34.5/23/11.5/0/0, and
background opacity = `--p`: exactly linear, then flat. The title sits inside the bar from p ≥ .75. At 390 the tab
bar shows, switches views and opens the Settings sheet. It is hidden at 800/1280. Under reduced motion, 0 running
animations after scrolling. The only hit-test miss is a card's rename button that has scrolled under the sticky bar (expected).

Recordings (1280 and 390, light + dark, slow scroll → browse → back to top → tiny scrolls):
`docs/ui-recordings/072-large-title-{light,dark}[-390].webm`.
