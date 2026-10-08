# 170 · The URL is the view (shell item 3, 2026-10-09)

- Hashes: `#campaign`, `#campaign/<slug>`, `#campaign/new`, `#analyze`, `#review[/<job>]` (review.js), `#editor`
  (Pick a clip, 171), `#editor/<job>/<clip>` (editor.js), `#schedule`, `#publish`. Stepper/campaign clicks set the
  hash (`go()`); `routeHash()` shows the view. Reload, back and forward restore it.
- Bare URL → the last view used, per user (`localStorage clipflow_last_view_<user id>`), after the session is known.
- Fix: `routeHash` is registered before the deferred lane-b scripts, so it closes the other lane-b page first —
  Review → Editor no longer leaves the old job list above the Editor (two pages restoring each other's sections).
- Tests: router.spec (hash per step, reload/back/forward, bare URL → last view, campaign hash); review.spec expects
  `#analyze` after Analyze.
