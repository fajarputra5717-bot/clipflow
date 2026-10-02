# UI audit · progress states outside the job status island · 2026-10-02 (main @ 6fd43cf)

Rule (owner, 2026-10-02; CLAUDE.md since 090): the island is the ONLY global progress indicator. List rows
(job cards, Publish queue) may show per-item progress, but only as a small capsule in island style (same
shape, colours, motion). Any separate bar/spinner/toast design for progress = **Medium**.

Static audit of `frontend/html/index.html` (no browser run).

## Findings
1. **Medium · Import job cards carry their own progress bar.** `createJobCard()` / `patchJobCard()`
   (`index.html:1650`/`:1662`) render `.mini-bar` (track/fill/pct) per running job in `#currentJobs`, a separate bar design
   (track + fill + %), not an island-style capsule. Placement is fine; the style isn't.
2. **Medium · Publish queue rows show progress.** `renderQueueJob()` (`:1712`) adds `.progress-msg` (`:1720`) and
   `miniProgressBar()` (`:1729`) for busy jobs: separate bar
   design again; should be the island-style capsule.

## Uses the island (OK)
- Candidate preview/final/thumbnail tasks: `watchCandidate()` → `setCandidateActiveTask()` (`:2347`) →
  `updateJobIsland()` + `renderJobOverlay()`.
- `#jobOverlayList` rows with `progressRing()` (`:2623`): the island's own "+N" overlay.

## Not counted
- `setBusy()` button spinners (`.is-busy`, `aria-busy`, e.g. "Uploading…" `:2739`): short action feedback,
  not job progress. Flag if the owner wants them counted.
- `progressCombo()` (`:1489`) has no callers (dead code).
