# 052 — UI polish pass (R-11)
Date: 2026-09-29 · Commit: see `git log --grep R-11` · Files: frontend/html/index.html · UI v2.1104

## What changed
- **Motion.** In-panel feedback now takes 100–200 ms: buttons 320→180, choices 300→180, inputs 280→150, stars
  250→150, thumbnail pick pop 480/420→200. Larger transitions take 300–500 ms: tab/candidate switch 450–550→300–400
  (the JS `setTimeout` was 540→400 to match), and the drawer entrance is 340. Progress ring 900→400.
  `.mini-bar-fill` animates `scaleX` instead of `width`.
- **Edit drawer.** It opens with `display` plus an opacity/translate entrance (no `max-height` morph). A card re-rendered
  by `watchCandidate` while editing gets `.no-enter`, so the entrance doesn't replay every 2 s poll. The primary path
  (Subtitle text + style + live preview → Apply) stays open. Description and Thumbnail are `<details class="edit-more">`
  with a one-line summary ("Not written yet" / "3 options · picked"), closed by default. Their open state lives in
  `editMoreOpen` and survives re-renders. Their AI/upload buttons moved out of the summary into the section body.
  Version history uses the same trailing chevron. Apply / Final render sit in a **sticky glass action row**
  (`.edit-actions`), so Apply is always reachable.
- **Glass** only on the drawer surface and the sticky action row. The chips over the video lost their
  `backdrop-filter` (solid 62 % black), so the preview stays flat.
- **Loading/disabled.** One helper, `setBusy(el, busy, label)`: it disables the control (`aria-disabled` for
  `<label>` uploads), sets `aria-busy`, adds `.is-busy` (a spinner, 0.8 opacity instead of the 0.4 disabled fade), and
  restores the original label. It is used by Analyze, Get another hook, Fix typos, Generate description, Generate
  thumbnails, thumbnail upload, watermark upload, Save settings, and the new busy states on **Apply changes** and
  **Final render** (those two had no double-submit guard before). Busy buttons rendered from server state get the same
  class.
- **Reduced motion.** The caption preview loop is JS `setInterval`, which the CSS reduce rule can't stop. It now
  renders the static line under `prefers-reduced-motion` and re-renders live if the preference changes. JS
  `scrollTo`/`scrollIntoView` use `behavior:auto` under reduce (the CSS `scroll-behavior` rule doesn't cover explicit
  JS `smooth`).
- **Keyboard.** Tabs are `role=tab` with a roving tabindex, `aria-selected`/`aria-controls`, Enter/Space and ←/→. They
  were unfocusable `<div>`s (ui-audit §1). Edit has `aria-expanded`. There is a global `:focus-visible` ring for
  buttons, `[role=button]`, summaries and links.

## What I verified (headless Chromium 153, :8081 preview, real completed job)
Keyboard tab switching and aria state. Drawer entrance: `drawerIn` running at 120 ms (opacity 0.83), and `none` under
reducedMotion=reduce. Sections start closed and the Thumbnail open state survives a simulated `watchCandidate`
re-render with no replayed entrance. The caption timer runs normally and is absent under reduce. `setBusy` round-trips
label, disabled, aria-busy and spinner. The action row is `position:sticky` with blur and stays pinned at the viewport
bottom while scrolling the drawer. The video chip has no backdrop-filter. The R-12 click-through and R-13 motion
suites were rerun: pass, no console errors.

## What I did NOT verify
I did not click Apply, Final render or any AI button against the backend (real renders / billable calls). Their
busy wiring was checked by calling `setBusy` directly. Not checked: real-device feel, Safari's
backdrop-filter cost on the sticky row, and screen-reader output.
