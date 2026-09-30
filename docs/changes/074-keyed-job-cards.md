# 074 · Import job cards patched in place (no poll flicker) · index.html · v2.1115

**Problem.** Every poll rebuilt `#currentJobs` with `innerHTML` (`loadCurrentJobs`) or swapped a
card's `outerHTML` (`refreshJob`), so cards re-mounted, `cardIn` replayed and bars restarted from
their initial state. The inner status line used `isBusy()`, whose `BUSY` list lacks `processing`,
so a job at "Processing 5%" said "Finished — moved to Publish". "Waiting for worker" showed twice.

**Change.**
- `syncCurrentJobs(jobs)`: keyed by job id. Existing card → `patchJobCard()` (text-node
  `nodeValue`, badge class, bar `transform`, action buttons rebuilt only when their set changes).
  New card → `createJobCard()` + `cardIn`. Gone card → `leaveJobCard()` (WAAPI height/padding/
  margin/opacity collapse, 450 ms; removed at once under reduced motion). Only new cards or a real
  reorder touch the tree. `refreshRunningJobs()` (2.2 s monitor, same endpoint) now also syncs the
  list, so every card stays live, not just the active one. A failed fetch keeps the cards.
- `.mini-bar-fill` transition 600 ms `--ease-out` from the previous value (node persists).
- Status line: `jobStatusLine(j)` = "Finished…" only for review/completed, else `message ||
  stageLabel(status)`; hidden when equal to the badge text. The line under the title is gone.
- Job UUID + URL moved into `<details class="job-details">` ("Details"), open state survives polls.
- Island: `#islIcon` keyed like `#islLead` (thumbnail `<img>` no longer re-mounted per poll), "+N" /
  texts via `setText`, a failed event keeps the ring/bar where the job stopped (was reset to 0).
  `#jobOverlayList` rows are keyed and patched the same way.

**Verified** (headless Chromium, mocked API, 3 jobs polling for 15 s, video recorded):
MutationObserver on `#currentJobs` subtree: 0 added / 0 removed nodes; the same 3 card nodes;
card rects identical in every frame (1 layout state); bar scale never decreases, 123 distinct
interpolated values. Leave/enter: exactly 1 removed + 1 added node. Reduced motion: transitions
0 s, bars step per poll, leaving card removed without animation.
