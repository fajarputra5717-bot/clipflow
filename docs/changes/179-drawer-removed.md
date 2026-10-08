# 179 · Old job list/detail + edit drawer deleted (lane-b merge follow-up, 2026-10-09)

- After 173–174 (Thumbnail, Watermark, Export tabs; "All edits" gone from Review) every drawer piece has a home in the
  Editor page. Removed from index.html (parser-driven dead-code pass, ~700 lines): the classic queue list + job
  detail (`loadQueue`, `openQueueJob`, `renderDetail`, `renderCandidate`, `renderQueueJob`), the drawer
  (`toggleCandidateEdit`, `applyEdits`, edit tabs, caption presets/keywords/position, Submagic row, versions,
  thumbnails, rating, rule-fix, upload) and `openClassicEdit` + their handlers. `#queueSection` stays as an empty host.
- Kept/ported: the Approve & schedule sheet (opened from Review cards); render-warning chips (loudness, "Final
  outdated · re-render") now on Review cards (review.js, was drawer-only). Island clip tasks open `#review/<job>`.
- Tests: edit.spec deleted; classic-list tests removed (jobs, editor); rules.spec + schedule.spec run on the Review
  page via the new `mockReviewClips()` fixture; shell.spec's Editor step → Pick a clip; live.spec → Review page.
  188 passed. Leftover drawer CSS is inert and goes in a later cleanup.
