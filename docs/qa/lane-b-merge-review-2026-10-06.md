# lane-b → main merge review (Review page 9089c71 + editor tasks 1–3) · **MERGE NOT OK** · 2026-10-06
Staging (lane-b tree at 9089c71; no newer lane-b commits), QA members qa_a/qa_b (own data).

## Blocker
1. **HIGH · cut words stay on screen** (3597000 #1, still unfixed): captions are burned at source times then cut with
   the video, so a line spanning a cut keeps the removed words ("FINALITY GAS AJA", "GOALIN AJA AMAN" after cutting
   "gas aja goalin"); a cut curse/SARA word stays readable. `frames/lane-b-3597000-cuts.jpg`.

## Passed
- Cross-user: A on B's clip → **404** on GET editor, PUT hook-title, PUT cuts, PUT fix-length; Review page lists only
  the caller's jobs.
- Quick fixes live (qa_b's clips): Add tags (description stripped → hashtag chip red → fix-rule → green) ✓; Trim
  (fix-length 30 → preview 30.0 s, karaoke sweep intact in 3 frames, `frames/lane-b-merge-trim.jpg`) ✓; Fix watermark
  = regenerate-preview 200 ✓ (missing-asset path itself verified in 099).
- Karaoke timing after cuts: mapped word highlighted at the computed output time ✓ (text issue = blocker above).
- Hook card (task 1): shows for its 2.5 s, below the watermark ✓. Timeline (task 2): Playwright ✓.
- Playwright (lane-b suite on staging): 113 passed, 5 skipped, 0 failed; rule_checks tests OK.

## vs mock (steps 4–5; `frames/lane-b-9089c71/`) — differences, not blockers
- Step 4: job picker first (mock: clip cards by hook score); mobile title squeezed one word per line (Low).
- Step 5: structure matches (eyebrow, title, reason, player left, tabs right, sticky bar). Missing vs mock: score chip
  + rule chips in the header, presets/keyword section in Captions (still in the old drawer), "Approve & schedule" in the
  sticky bar. **Low bug:** the stepper highlights "Analyze" as active on the Editor page.
