# 226 — phone trim handles get their full 44 px hit area (Lane C Medium, after 224/225)

The timeline content (`.ed-tl-inner`) sat flush against its horizontal scroller, so the clip-start handle (at x 0)
and the clip-end handle (at the last second) lost half their width plus their ±13 px phone hit area to the scroller's
clip (measured 23 / 32 px at 390). The inner now has a 24 px margin at both ends (`TL_PAD` in editor.js for the
follow-scroll); every pointer position is already measured from the inner's own rect, so seeking, cuts, zoom markers
and drag-scrub are unchanged. editor.spec asserts ≥ 44 px for both handles at 390 (elementFromPoint scan).
