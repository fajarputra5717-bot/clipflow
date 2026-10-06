# QA review · 44354aa · fix(auth): login limits per username+IP, looser per-username cap (139)
Reviewer: Lane C · 2026-10-07 · Lane A's staging verification 15/15 (docs 138–140, lane-a users) cited. QA: staging login sets cookie `clipflow_staging_session` (140) ✓; UI writes on :8080 work in QA's live runs (138) ✓. No findings.
