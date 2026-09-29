# 068 — Sidebar = navigation; Settings/Watermarks as sheets; ClipFlow mark
Date: 2026-09-29 · Commit: see `git log --grep "068"` · Files: frontend/html/index.html, frontend/html/clipflow-mark.svg, CLAUDE.md · UI v2.1107

## What changed
- The sidebar holds a brand row (new **ClipFlow mark** SVG + wordmark + collapse), then navigation and a footer.
  - **Navigation** has 4 rows (`[data-nav]`, 44 px): Import, Publish, Watermarks, Settings. Each has a 20 px line
    icon at 1.8 stroke.
  - An absolutely positioned `#navIndicator` moves between rows with `transform` on `--ease-spring`/`--dur-3`.
    `syncNav()` sets `aria-current` (`page` for views, `true` for an open sheet).
  - **Footer:** the Appearance row (sun/moon cross-fade + "Light/Dark" value) replaces both header theme toggles.
- **Removed:** Quick actions (the polling already refreshes) and the Editing tips block. The tip now lives in the
  Publish empty state. A 44 px **refresh icon** (`#refreshView`, a single 450 ms spin, skipped under reduced motion)
  reloads the current view. The "R" letter logos (header, sidebar, topbar chip) now show the mark, which is also the favicon.
- **Sheets:** `#settingsSheet` and `#watermarkSheet` hold the existing panels unchanged: same ids and the same load and
  save code. Each is a centred dialog (`role=dialog`, `aria-modal`) that scales .96→1 and fades over a blurred
  backdrop. On ≤600 px it is a bottom sheet. It closes on Esc, a backdrop click or ×. While a sheet is open
  `#appShell` is `inert`, Tab is trapped in the sheet, and focus returns to the opener on close. Closed layers stay
  `visibility:hidden; pointer-events:none`.
- On the narrow drawer, choosing a nav row also closes the drawer.

## Decisions & trade-offs
- Settings and Watermarks became sheets rather than views: they are management tasks, not places. 069 and 071 restyle
  their contents.
- The tabs pill stays in sync (`showTab` → `syncNav`) until 072 removes it.

## Verification (headless Chromium, :8081, /api mocked; light/dark × 1280/800/390)
0 errors. No clickability failures, including with each sheet open. Per size and theme: Publish selects the view
and the indicator. Settings opens with the shell inert and focus inside. Esc closes and returns selection to
Publish. A backdrop click closes Watermarks. The theme row flips `data-theme` and its label. Refresh works. Under
reduced motion, 0 running animations for nav, sheet open/close and refresh.
