# QA review · 556cca7 (lane-b) · Playwright smoke harness (tests/ui)

Reviewer: Lane C · 2026-10-02

Ran from a scratch copy of `origin/lane-b:tests/ui` (no node_modules written into Lane B's worktree), default
mocked mode (never creates a job): **22 passed, 4 skipped, 0 failed, 27.4 s**, desktop 1280 + mobile 390.
Skips include the opt-in `live.spec.js` (needs CLIPFLOW_UI_LIVE + key).

Covered: import validation + language payload, keyed job cards (074), publish list, edit drawer + tabs, the
"nothing clickable" overlay regression, island show/expand/hide. Fails on page errors, console errors and
unexpected dialogs. Good base for the P1 gate.

## Gaps (QA will add cases here, coordinated with Lane B)
1. No case for the island-capsule rule (row progress must use the island style; no separate bars).
2. No case for `render_warnings` chips (loudness, campaign_watermark).
3. No `/api/activity` failure case (keep last tasks, retry, console log — P0 item).

## Not verified
- `live.spec.js` against the real backend.
