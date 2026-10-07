# 149 · Lane-b production merge: Review page + Editor page in the stepper; old panel kept as "All edits" · index.html, review.js, compose images

- **Why:** Lane C MERGE OK at lane-b 202d39a (qa d8517f5; cuts HIGH closed 2ac96e7) and 1758b6c (task 4 zoom, qa
  c5b3e7b). Merged with `--no-ff` in two steps: 0a81ae5 (202d39a) and e9ffad4 (1758b6c, not newer: Lane B is on
  task 5). Rollback point: tag `pre-laneb-merge`. No DB schema change (only `edit_spec` keys hook_title / cuts /
  zoom; old code ignores them).
- **Navigation (d8eed01):** stepper/tab-bar Review → the Review page (`#review`, editor/review.js; filters, rule
  chips, Approve, fixes); leaving it clears the hash. Editor step → the Editor page (`#editor/<job>/<clip>`,
  editor/editor.js; hook title, timeline, cuts, fillers, zoom), highlighted + title "Editor" while open; it stays
  enabled afterwards and reopens the last clip. Review cards also get **Approve & schedule** (146 sheet) and
  **All edits** (the old job detail + edit panel for that clip).
- **Drawer NOT removed (owner decision 2026-10-07):** parity table: no home yet in the Editor page for caption
  style/font/size/animation + presets + keywords, subtitle text + Fix typos, Watermark/Effects/Audio/Export tabs,
  thumbnails, description, new hook, versions, Submagic, Final render, Approve & schedule. Each drawer piece is
  removed when P4 gives it a home in the Editor page.
- Lane-b "hook" one-liners are normal code now (comments gone); lane-b change docs numbered 150–156; the duplicate
  `lane-b-payouts.md` dropped (131 is it).

**Verified:** unit tests OK (all 14 files), caption mirror OK, UI suite 149 passed (specs moved to
`classicQueue()` for the old panel + new navigation spec); images import-tested (backend + routes_editor, worker +
render_steps, sender, notifier); deployed idle: 6/6 containers up, backend healthy, /editor/*.js|css 200;
prod read-only: `editor_state` for an admin final → no hook/cuts/zoom (renders unchanged).
