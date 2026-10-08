# 182 · Phone touch targets ≥ 44 px on every page (Lane C Medium from qa 7348e15, 2026-10-09)

- One phone rule (≤ 600 px) at the end of index.html, which also covers Lane B's Review/Editor (same document;
  `body …:not()` outranks editor.css's compact rules): buttons, summaries, selects, Review links, the editor's
  Back link and Timeline summary get `min-height: 44px`. Controls drawn at a fixed size keep their look and get an
  invisible 44 px hit area: switch (`::before`), swatches, rename pencil, island Cancel, toast action, overlay close.
- Desktop stays compact on purpose: top-bar icons and stepper nodes are 36 px per the owner's shell v2 spec
  ("36 px hit area desktop, 44 px phone"); Lane C's 1280 findings are left for the owner to decide.
- Fix: a direct `showTab()` now also leaves Pick a clip (its filters showed on Schedule/Publish in the tour).
- Tests: touch.spec (every visible control at 390 on all 8 views + all 6 Editor tabs has a ≥ 44 px target, counting
  ::before/::after hit areas; fails if the Editor mock can't render); overlays.spec: Settings/Watermarks sheets fit
  390 when opened from the account menu (Lane C Low). The tour's editor mock gained thumbnail/watermark/export.
  UI 194 passed.
