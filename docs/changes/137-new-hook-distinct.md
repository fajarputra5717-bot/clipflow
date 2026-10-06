# 137 · Bug: "Get another hook" could return a moment an existing clip already had → used ranges, validation, retries · main.py, shared/hook_ranges.py, index.html

- **Cause:** the avoid list held only the job's CURRENT clips, so a replaced clip's range was forgotten and could come
  back; the transcript sent was cut at 15 000 chars, steering long videos to the same early moments.
- **Per-job memory:** `jobs.used_hook_ranges` (JSONB `[[start, end], …]`) = every range the job's clips have had;
  each new hook adds the replaced range and the new one (`hook_ranges.merge`, newest 200).
- **Prompt (new-hook only; the frozen main hook prompt is untouched):** lists used + current ranges as "already
  used, do not pick these (nor anything overlapping or starting within 10 s of them)"; transcript limit =
  `HOOKS_FULL_TRANSCRIPT_MAX_CHARS` (was a hard-coded 15 000).
- **Server-side validation:** `hook_ranges.too_close` rejects an answer overlapping a used range by > 30 % of the
  shorter clip or starting within 10 s of one; up to 2 retries with the rejected range added; still too close →
  409 "No new distinct moment found: …" (shown as is), never a duplicate.

**Verified:** `tests.test_hook_ranges` OK (30 % boundary, 10 s starts, merge); harness passed; backend deployed
(column present). **Staging (24ce3eb), real job:** 3 consecutive "Get another hook" clicks on one clip →
429.0–463.3 s, 220.0–255.0 s, 308.3–344.1 s: each distinct (hook_ranges.conflict) from every range used before it;
`used_hook_ranges` keeps the originals + the 3 new ones.
