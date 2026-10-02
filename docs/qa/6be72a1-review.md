# QA review · 6be72a1 · 111 keyword highlight: AI-picked, stoplists, tap to toggle, colour, baked into the ASS (P1)
Reviewer: Lane C · 2026-10-02 · `edit_spec.keywords` (≤ 20, explicit `[]` = none) + `keyword_color` validated;
`pick_keywords()` one utility call per clip at preview build, filtered to real clip words ≥ 3 letters not on the job
language's stoplist, never overwrites user choices, never fatal; `make_ass()` colours keywords with `\1c`+`\2c` in
every animation mode and resets after. Known (Lane A follow-up): default yellow = karaoke highlight on yellow
styles. Re-check: gate-P1 (fresh campaign renders with green keywords).
