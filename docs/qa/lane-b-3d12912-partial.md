# lane-b 3d12912 (7b-7e, 6 source_watch) · partial, NOT a verdict · 2026-10-09
Merge: NOT YET (real renders + Export actions not run, blocked on staging credentials).
Done: Playwright on staging :8080 (lane-b HEAD 3d85c4d, tests from that SHA) 187 passed / 5 skipped / 0 failed. Static read of source_watch.py + routes_editor/main diff.
Staging backend image predates 3d12912 (no shared/source_watch.py inside); frontend is the bind-mounted tree = 3d85c4d.
source_watch.py:
1. Medium · baseline with a failed /streams listing records only /videos; the next good run returns up to 15 old streams as "new" (backlog flood). Retry baseline until both tabs list, or store baseline per tab.
2. Medium · ids are marked seen when returned, before the caller creates the job: a failed job create (507, DB error) loses the video for good. State is also per channel, not per user: a second user watching the same channel gets [].
3. Low · read-modify-write of <channel_id>.json has no lock (two callers: duplicates/lost marks). SEEN_CAP trim sorts by a per-check shared stamp, ties drop arbitrarily.
4. Not verified: flat-playlist returns live_status for /videos entries (tests use a fake runner); unit tests not run (no pytest on host).
