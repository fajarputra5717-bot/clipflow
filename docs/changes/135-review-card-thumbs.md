# 135 · Bug: Review job cards showed empty grey thumbnails → first clip's thumbnail · main.py, index.html

`renderQueueJob()` used `j.candidates[0]`, but `GET /api/jobs` never returns candidates, so `.queue-thumb` stayed
empty. The list now returns `thumb_candidate_id` (first clip by clip_index with a thumbnail_path) and the card loads
`/api/jobs/{id}/candidates/{thumb_candidate_id}/thumbnail` through `mediaUrl()` (same ownership guard).

**Verified (prod, read-only):** queue = 24 jobs, 24 with thumb_candidate_id and 24 with a source title (134);
thumbnail GET 200 image/jpeg. Harness jobs.spec 6 passed (+ thumb src).
