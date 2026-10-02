# UI audit · progress states outside the job status island · 2026-10-02 (main @ 6fd43cf)

Rule (owner, 2026-10-02): any progress state that doesn't use the job status island (`#island`,
`updateJobIsland()`) = **Medium**. Note: main's CLAUDE.md doesn't state this rule explicitly yet (it says
only that the island is "driven only by `updateJobIsland()`"); Lane A should add it.

Static audit of `frontend/html/index.html` (no browser run).

## Findings
1. **Medium · Import job cards carry their own progress bar.** `createJobCard()` / `patchJobCard()`
   (`index.html:1650`/`:1662`) render `.mini-bar` (track/fill/pct) per running job in `#currentJobs`, parallel to
   the island. (074 design; owner to confirm whether the card bar is exempt or must go.)
2. **Medium · Publish queue rows show progress.** `renderQueueJob()` (`:1712`) adds `.progress-msg` (`:1720`) and
   `miniProgressBar()` (`:1729`) for busy jobs.

## Uses the island (OK)
- Candidate preview/final/thumbnail tasks: `watchCandidate()` → `setCandidateActiveTask()` (`:2347`) →
  `updateJobIsland()` + `renderJobOverlay()`.
- `#jobOverlayList` rows with `progressRing()` (`:2623`): the island's own "+N" overlay.

## Not counted
- `setBusy()` button spinners (`.is-busy`, `aria-busy`, e.g. "Uploading…" `:2739`): short action feedback,
  not job progress. Flag if the owner wants them counted.
- `progressCombo()` (`:1489`) has no callers (dead code).
