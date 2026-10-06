# d00d85c (lane-b) fix(editor): cut words disappear from burned captions — QA 2026-10-07

Verdict: **fixed, verified live on staging** (clip 884938b3 / job b0a4ed97, user lane-c-a).
- Cuts [[2.58,3.16],[7.96,8.16],[10.70,11.46]] ("yang cukup", "Anjik" ×2). Preview 31.467 s (expected 31.46).
- Preview + final ASS: 0 cut words; kept words re-timed ("ORANG PUNYA POSISI", "KEBAKAR LAGI", "SIAP").
  The ANJIK at 29.02 s is a third, uncut occurrence (correct).
- Karaoke sweep intact across the seams (frames/lane-b-d00d85c-cuts.jpg, 3 frames).
- Final: 1080x1920, 31.467 s, -14.1 LUFS / -1.1 dBTP.
Closes the HIGH from lane-b-merge-review-2026-10-06.md.
Not verified: cuts inside a hook-title card window; cuts + filler accept on the same clip (d419552).
