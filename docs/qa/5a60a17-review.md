# QA review · 5a60a17 · 102 island feed: last state + backoff, running allow-list, Submagic indeterminate (closes gate-P0 #5)

Reviewer: Lane C · 2026-10-02 · code review (Playwright mocks don't stub /api/activity yet)

- Failed `/api/activity` poll: keeps `activityTasks`, `console.warn` with count + retry delay, exponential backoff
  (POLL_INTERVAL·2ⁿ, max 60 s), reset on success. ✓
- `JOB_RUNNING` allow-list replaces the `JOB_RESTING` deny-list. ✓
- Submagic: `percent: None` → island `.is-indeterminate` (spinning quarter ring, no number, aria text without %),
  reduced-motion guard. ✓

## Findings
1. **Low · `reanalyze_queued` is missing from the allow-list** (`backend/app/main.py` `JOB_RUNNING`) and from the
   frontend `BUSY` list (`index.html:1283`, pre-existing): a queued re-analysis/retry isn't in the island until it
   turns `processing`. Add it to both.
2. Info · activity job rows are currently unused by the frontend (`kind!=="job"` filter); the allow-list matters for
   future consumers.
