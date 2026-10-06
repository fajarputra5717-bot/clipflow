# 649ae25 (lane-b) feat(review): filters campaign/job/status, campaign grid across jobs — QA 2026-10-07

Cross-user (P1.5 rule): **OK.** On staging lane-c-b GET /api/review/clips?job=<lane-c-a job> (also &status=all,
campaign=ime-roleplay) returns 0 clips and a null title. No leak. lane-c-a sees only its own job.
Bugs:
1. Low, spec: review.spec.js:86 "quick fixes + approve…" fails 3/3 on [mobile] (staging and git-served). The click on
   [data-rv-approve] times out because the element is "not stable": html has scroll-behavior:smooth (index.html:142), so
   Playwright's scroll into view keeps animating. Scrolling first and then clicking works. Not a user bug. Fix the spec:
   scrollIntoViewIfNeeded + toBeInViewport before the click, or set reducedMotion in the fixture.
2. Low: PUT /api/review/filter stores any job id, another user's included, and echoes it back. Reads ignore it, so
   nothing leaks. Store only owned ids, or fall back to "all".
3. Low: review.js:227-242 fix()/approve() clear setBusy only on error. On success they depend on refresh() re-rendering
   the button. In the mock, both .rv-fix kept spinning after refresh. If a fix leaves the check unchanged, the button
   stays busy until reload.
Suite on staging: 120 passed, 1 failed (#1), 5 skipped. The 8 failures seen at d00d85c came from running the
d00d85c spec copy against the 649ae25 frontend, which rewrote review.spec.js. They don't reproduce.
