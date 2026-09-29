# 050 — Left sidebar + simplified Import (R-12)
Date: 2026-09-29 · Commit: see `git log --grep R-12` · Files: frontend/html/index.html · UI v2.1102

## What changed
- The right-hand `.rail` is gone. Its contents moved into a left `<aside id="sidebar">` in a new `.app-shell` grid:
  Workspace header → Quick actions (Refresh import / Refresh queue) → Editing tips → Settings disclosures
  (Advanced settings · system/publishing, Watermark · asset library). The element IDs are unchanged, so every existing
  handler still works.
- Desktop (≥1000 px): the sidebar is a sticky 272 px column. The sidebar-icon button hides it (`body.sidebar-collapsed`,
  remembered in `localStorage`), and a twin button at the left of the header brings it back.
- Narrow (<1000 px): the sidebar becomes an off-canvas drawer over `#sidebarScrim`. It closes on Escape (focus
  returns to the opener), a scrim click, or a breakpoint change. `aria-expanded` is set on both toggles, and the
  hidden sidebar gets `inert`.
- Import: composition / facecam / platform and the subtitle-defaults note are folded into one `<details
  id="importOptions">` ("Options"), whose summary shows the live choice (`70 : 30 · Auto facecam · YouTube Shorts`).
  The URL, job name and Analyze stay on top. What gets submitted is unchanged.
- Small fixes: nested settings-group summaries all showed "−" (the selector was `details[open] summary`, now `> summary`).
  Sidebar icon buttons no longer pick up the dark-theme button fill.
- Wiring: `[data-sidebar-toggle]` and `#sidebarScrim` in the delegated click handler, Escape in the keydown handler.

## Decisions & trade-offs
- The "Performance · leaderboard & correlations" disclosure from the old sidebar is **not** added: R-23 (backend) is
  not rebuilt yet. Add it there.
- Collapse drops the grid column instantly while the sidebar slides out with `transform`. Nothing animates a
  layout property.
- Click-through guard (the old "nothing clickable" regression): every closed overlay layer (scrim, drawer) is
  `visibility:hidden; pointer-events:none`, and the scrim's z-index (110) is below the drawer's (120) and above the
  sticky topbar (50).

## What I verified
Headless Chromium 153 (Playwright) against the :8081 preview, at 1280 light, 1280 dark and 390 light. An
elementFromPoint hit test on every visible button/summary/input/tab found nothing covered on load, with the sidebar
collapsed, with the drawer open, or after closing it (by Escape and by scrim click). The Options summary updates.
Settings disclosure and tab switching work. No console errors. Screenshots were inspected.

## What I did NOT verify
Real touch devices, Safari/Firefox, screen readers. Saving settings and uploading a watermark from the new location
(same IDs and handlers, not clicked through to the API).
