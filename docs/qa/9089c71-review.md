# QA review · 9089c71 (lane-b) · Review page = flow-preview step 4 (job picker, clips by hook score, rule chips)
Reviewer: Lane C · 2026-10-06 · staging, logged in as QA member qa_a (real UI on :8080)
- Uses only existing scoped APIs (/api/jobs, /api/jobs/{id}, /api/activity) → main's ownership guard applies; live:
  qa_a sees only its own 2 jobs ✓. `shared/rule_checks.py` change (feeds main's approve gate after merge):
  tests/test_rule_checks_editor.py OK.
- Playwright (lane-b suite, staging): **113 passed, 5 skipped, 0 failed**.
- vs mock step 4 (`frames/lane-b-9089c71/`): app shows a job picker (job cards: title, thumbnail, campaign/status
  chips, delete) first; the mock goes straight to clip cards sorted by hook score with rule chips + Approve. Clip view
  after "tap a job" not captured (not verified).
## Findings
1. Low · mobile 390 px: campaign + status chips squeeze the job title into a narrow column, one word per line
   (`app-mobile-review.png`); the delete button is oversized next to it.
2. Low · desktop: job card leaves a large empty area right of the thumbnail ("Tap a job to review…").
**Merge: OK** (this commit). Note: lane-b as a whole stays blocked by 3597000 #1 (HIGH).
