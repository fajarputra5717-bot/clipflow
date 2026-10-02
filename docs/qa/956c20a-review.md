# QA review · 956c20a · 090 island is the only progress UI: GET /api/activity

Reviewer: Lane C · 2026-10-02 · deployed backend confirmed (live `GET /api/activity` → 200 `{"items":[]}` while idle)

Checked: new route under `/api` (auth middleware applies; not a file route) · frontend uses `api()` · island
merges activity rows in `allActiveTasks()`; click-registered tasks win over feed rows for the same candidate;
job rows are taken from `/api/jobs?scope=current`, not duplicated · CLAUDE.md states the rule (no new
spinners/bars/toasts; `setBusy()` stays).

## Findings (most severe first)
1. **Medium · the 2 row progress designs are still separate bars** (not changed by 090): Import job cards
   `.mini-bar` and Publish queue rows `miniProgressBar()` + `.progress-msg`. Per the owner's rule (2026-10-02)
   rows may show per-item progress only as an island-style capsule. See ui-progress-audit-2026-10-02.
2. **Low · feed errors are silent.** `api("/api/activity").catch(()=>null)` hides a 500 (e.g. a bad JOIN), so the
   island quietly loses candidate/Submagic tasks started elsewhere. Log once to the console at least.
3. **Low · job filter is a deny-list.** `JOB_RESTING` excludes known resting states; any new job status
   shows up as "running" in the feed until added. An allow-list of busy states (as for candidates) is safer.
4. **Low · Submagic percent is synthetic** (0 queued / 50 running), so its capsule sits at 50 % for minutes.
5. **Process** · no badge bump.

## Not verified
- The island with feed rows live (feed was empty during the check; fresh-import e2e had already finished).
