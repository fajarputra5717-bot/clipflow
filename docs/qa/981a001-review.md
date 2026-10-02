# QA review · 981a001 · 095 facecam layout decided per job (P0, QA 087 #1 / 091 #2)

Reviewer: Lane C · 2026-10-02 · deployed worker confirmed

`decide_face_layout()` detects every clip once (per-process cache `_FACE_CACHE`, ≤ 64 entries), stores
`jobs.face_layout = {mode, detected, total, fallback}`; strict majority with a face → `panel` (misses get the
median box), strict majority without → `full` (stray hits dropped); tie → `panel` only if ≥ 2 hits agree within
10 % of the frame, else `full`. Threaded into create_preview, render_final_candidate, thumbnails, the candidate
claim SELECT and the task dict (layout-threading invariant OK). Overrides log. 9 old jobs backfilled.

## Findings (most severe first)
1. **Medium · two-clip ties drop a real facecam.** With CLIP_COUNT = 2 (this box's default), a facecam stream
   where detection misses ONE clip is a 1/2 tie with < 2 hits → `full` for BOTH clips: the streamer's camera
   disappears from the whole job (before 095 only the missed clip lost it). A single detected hit on a facecam
   stream is usually a real cam; consider `panel` on a tie when the one hit sits in a corner/edge region typical
   for cams, or detect on more sample frames before deciding.
2. **Low · cache key ignores the source file's identity beyond its path.** A re-downloaded source at the same
   path with different content would reuse stale boxes for the process lifetime (unlikely; files are per job).

## Re-check
See gate-P0.md (fresh GTA RP job: no false-positive panel; Fandra job: facecam panel).
