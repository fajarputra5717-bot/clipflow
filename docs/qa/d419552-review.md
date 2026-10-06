# d419552 (lane-b) feat(editor): filler-word suggestions — QA 2026-10-07 (code read + Playwright)

- Suggestions are pre-struck but only become cuts on accept (never auto-cut): matches the spec.
- Accepted fillers go into the same `removed` list → same burn path as d00d85c, so caption removal is covered by that check.
- lane-b Playwright (editor specs) pass on staging and git-served.
Not verified live: an accepted filler on a real render; en list on an English job.
No bugs found.
