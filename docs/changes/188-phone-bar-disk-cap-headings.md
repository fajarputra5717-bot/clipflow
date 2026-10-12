# 188 · Phone top bar + island width, disk-wait 24 h cap, no "Step n ·" headings (2026-10-12)

- Phone top bar (≤ 600 px): with no island the page title (`#pageContext`) runs from the logo to the menu (was capped
  at ~65 px to clear the island). While the island shows, it owns the middle and the title is hidden (the page name
  stays in `#pageTitle` and the stepper's aria-label); the compact island is `islandCompactW()` = 150–240 px
  (390 px phone → 220), so "Transcribing Fandra mai…" fits next to the "+N" split, clear of logo and menu.
- Auto-import disk waits are capped: a `found` row blocked by the disk (507 reserve or the watch's pause_below_gb) for
  more than 24 h since it was found → skipped "Disk full for 24 h" (`auto_import.DISK_TIMEOUT`, in CONFIRMABLE →
  the Campaign page's confirm list). Verified in a throwaway Postgres + backend image.
- The old "Step n · …" eyebrows above the page headings are gone on every page (the stepper pill shows the step).
- Island single-spinner + "<verb> <subject>" labels were already done in 185.
- Tests: island.spec phone layout (title width idle, hidden + no overlap with the island). UI 211 passed.
