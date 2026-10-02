# 110 · Hook score stored and shown as "AI estimate" (P1 editor commit 4) · worker.py, main.py, index.html

**Found.** The hook prompt returns `score` (0–100) and analysis ranks/dedupes by it, but the candidate INSERT
never stored it: 0 of 28 clips had a score, so every `ORDER BY score DESC NULLS LAST` sorted NULLs.

**Now.** No prompt change (frozen Indonesian wording / eval baseline).
- Analysis stores `highlight["score"]` in `clip_candidates.score`.
- "Get another hook" uses its own prompt without a score → sets `score = NULL` (no stale estimate).
- UI: under the clip title, an "AI estimate N" chip (mockup's virality chip, run-badge tokens) next to the
  model's reason. No score (pre-110 clips, new hooks) → reason only.
- Existing clips can't be backfilled (hook results weren't kept).

**Verified:** fresh Windah import (job 6411fd75, campaign motionklip-windah) → scores 90 and 85 stored; the
clip card shows "AI estimate 90" with the reason; harness 28/28. Same import also confirmed 109 on a fresh run
(chips for both clips, content check ran: 0 flags). Note: fresh campaign clips have no description yet, so
their hashtag chip fails until "Generate description" or "Add hashtags".
