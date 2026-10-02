# 105 · Island allow-list includes reanalyze_queued (Lane C 102 Low) · main.py, index.html

A re-analysis waiting for the worker (`jobs.status = 'reanalyze_queued'`) didn't show in the island after 102's
allow-list. Added to `JOB_RUNNING` (`GET /api/activity`) and to index.html `BUSY` (idle badge via `_queued`).
Also: P1 backlog note in docs/roadmap.md (light compression before loudnorm for peaky sources, Low).

**Verified:** `'reanalyze_queued' in main.JOB_RUNNING` in the running backend; UI harness 22/22.
