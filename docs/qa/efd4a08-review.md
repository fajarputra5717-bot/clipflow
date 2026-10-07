# efd4a08 (lane-b) P4 task 7a: Editor Captions tab — QA 2026-10-07
Staging a5c3da5 (= efd4a08 + main through a781ffb). No new write routes: caption-preset, fix-subtitle-ai, new-hook and
candidate PATCH are main's. lane-c-b POST caption-preset / fix-subtitle-ai / new-hook on lane-c-a's job → 404 ×3, job style
unchanged.
Live: lane-c-a clip 884938b3 PATCH edit_spec.caption {impact, word_pop}, cuts/zoom kept → preview render logs "Caption preset
for this clip: impact + word_pop (edit_spec)"; preview ASS has Impact colours and 37 word-pop scale tags.
Playwright on staging a5c3da5: 181 passed, 0 failed (lane-b suite + qa-multiuser).
Checked, not a bug: Default style "Liberation Sans Bold" with Bold=-1 also appears in the earlier final; it's the default
font, not a named display font (fonts.py ass_bold None).
Not verified: Fix typos (AI call) and Get another hook live (each costs an AI call / a render; covered by Lane B + specs).
Merge: OK.
