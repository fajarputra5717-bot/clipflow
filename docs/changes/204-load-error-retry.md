# 204 · Publish / Schedule / Track: "Couldn't load …" + Retry (deep audit M5, 2026-10-13)

A failed load used to put only the server's detail in an error box ("boom", "Internal Server Error"). Now
`loadErrorHtml(what, key, err)` renders a plain lead ("Couldn't load the publish list." / "the schedule." / "your
numbers."), "Check your connection and try again.", the detail as small print, and a Retry button
(`data-retry-load` → `LOAD_RETRY[key]`, `setBusy` while it reloads). role="alert". Review and Editor already had their
own wording. Spec: load-errors.spec.js (mocked 500 then success after Retry, all three pages, both projects).
Deploy gaps (502/503/504, bare 404) still read "ClipFlow is updating… try again in a minute." via `apiError()` (184).
