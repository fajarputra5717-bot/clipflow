# Staging end-to-end check (Lane C)

One command: `QA_USERS_FILE=<json {"lane-c-a": "<password>"}> tests/qa/e2e/run.sh` (needs Docker access to the `clipflow-staging-*` containers and the Playwright module of `tests/ui`, auto-found under `/opt/clipflow/tests/ui/node_modules`).

What it does (about 15 min; analysis of the 4 m 44 s real video dominates):
1. waits for an idle staging queue; logs in as `lane-c-a` (refuses any other user that isn't `lane-c-*`, and any base URL that isn't localhost :8080/:8001)
2. imports the real YouTube video through the UI (cached source on staging; override with `E2E_URL`), and a second import at once; opens the island "+N" list, checks it lists both and changes live; screenshots a running job at 1440 and 390 (with the animations running)
3. waits for analyze → review (stage times from the worker log), opens the clip from the review list, in the editor changes the caption text, toggles two audio edits (Loud & punchy, Light compression), renders a preview, measures loudness before/after (ffmpeg ebur128 in the staging worker), approves → final render, checks the final has sound (≥ -30 LUFS, TP ≤ -0.9 dBTP)
4. opens Publish (dry run: asserts the run posted nothing)
5. repeats editor checks with phone emulation (390×844, touch): mute button, scrub tap, audio switch, no horizontal overflow
6. deletes the jobs it created (`E2E_KEEP=1` keeps them).

Output in `tests/qa/e2e/runs/<timestamp>/` (git-ignored): `report.md`, `video/<context>/*.webm`, `trace-*.zip` (`npx playwright show-trace`), a screenshot per step. Exit code 0 = all pass, 1 = a step failed, 2 = crashed.
Knobs: `E2E_USER`, `E2E_URL`, `E2E_KEEP=1`, `E2E_SKIP_FINAL=1`, `E2E_JOB=<job id>` (resume with an existing lane-c job, skips import/+N/shimmer), `E2E_OUT`, `E2E_REPORT_COPY=<file>`, `PW_MODULE`.
Limits: staging has no pot sidecar, so a never-downloaded URL may fail to download; keep the default video. The run uses the staging queue (one render at a time per stack): do not start it while another lane is rendering (step 0 waits).
