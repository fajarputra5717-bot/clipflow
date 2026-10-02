# 102 · Island feed hardening: errors kept visible + backoff, running allow-list, Submagic indeterminate (pre-P1 #4, QA Low #5) · main.py, index.html

The 090 fold-ins Lane C listed (they hadn't reached Lane A):
- **Errors:** `/api/activity` failures are no longer swallowed. The island keeps the last good state,
  `console.warn` says so, and the next activity fetch backs off `POLL_INTERVAL × 2^n` (max 60 s); success resets.
- **Allow-list:** `GET /api/activity` lists jobs whose status is in `JOB_RUNNING` (queued, processing,
  downloading, transcribing/transcribed, analyzing … = index.html `BUSY` + `processing`) instead of "anything
  not resting"; an unknown status shows nothing rather than a phantom task.
- **Submagic:** `percent: null`, label "Submagic: queued" / "Submagic: processing". The island renders
  `indeterminate` items with a spinning quarter ring, no %, and no % in aria-label / live region; reduced
  motion → static ring.

**Verified** headless with a stubbed feed: Submagic item → island `is-indeterminate`, aria "Test clip: Submagic:
processing", no %; then the feed returns 500 → island keeps the item, 3 warnings, requests at 0.9 s, 7.5 s,
18.5 s (backing off); idle `/api/activity` → `{"items": []}`.
