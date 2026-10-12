# 186 · Auto-import: undated / unknown-length videos are skipped (Lane C P3 gate, 2026-10-12)

- QA P3 Medium (docs/qa/gate-P3.md): a video without an upload time (past the RSS window or a feed failure) was
  imported on a fresh check. Now `skip_reason()` always skips it: "No upload time" ("Older than the watch" when the
  channel's seen-list is stale). It shows in Recent imports with that reason; import it from Analyze if wanted.
- QA P3 Low: an unknown duration bypassed the per-watch duration window. Now skipped: "Unknown length".
- Trade-off: a feed hiccup during a check can skip a genuinely new upload (visible, never silent) instead of risking an
  import of an old one.
- Tests: unittest auto_import updated (7/7).
