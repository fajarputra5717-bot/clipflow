# QA review · 5ed63ce (lane-b) · retention: silence trim off by default, word-gap pauses, 40 ms crossfade

Reviewer: Lane C · 2026-10-02 · library only (not wired into worker.py on lane-b or main)

Checked: `SILENCE_TRIM_DEFAULT = False`; `word_gap_silences()` handles overlapping words (running max end);
crossfade arithmetic: each segment next to a cut is extended by h = min(crossfade/2, shortest keep/2) into
the removed part and joined with `acrossfade d=2h`, so each join adds and removes exactly 2h: audio length ==
video length (no A/V drift); `MIN_CUT` 0.10 s > crossfade 0.04 s keeps the extension inside the removed gap;
last segment bounded by `duration`. Unit tests on origin/lane-b: **23 OK**.

## Findings
1. **Low · first-segment clamp can drift.** `a0 = max(0.0, s - h)` for i > 0 shrinks a segment's lead-in only if
   s < h, i.e. a cut ending within 20 ms of the clip start: then that join removes more audio than it added
   (≤ 20 ms drift). Practically unreachable with `MIN_CUT` + pad, but untested.
2. **Low · karaoke re-timing after trim** relies on `remap_times()` (unchanged here); no test combines word-gap
   trim with the caption word list `make_ass` consumes. Needed before wiring.

## Not verified
- Audible result (c3f9474's level-dip/click metrics were not re-run by QA).
