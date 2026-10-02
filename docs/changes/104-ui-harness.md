# 104 · Lane B's Playwright UI harness on main (P1 start) · tests/ui

Cherry-picked `556cca7` from `lane-b` (as `ddf914c`): `tests/ui/` only (mocked-API smoke tests for the import
form, job list, edit panel, overlay "nothing clickable" regression, job island; opt-in live read-only mode;
one command `tests/ui/run.sh`, README for Lane C). The earlier lane-b commits (silence-trim default, trim
check script, publishing research doc, payouts with QA's open Medium) are NOT merged yet; they come with
the phase that uses them.

**Verified:** `tests/ui/run.sh` on main @ 103 → 22 passed, 4 skipped (live mode + desktop-only), 24 s.
P1 commits run it before committing.
