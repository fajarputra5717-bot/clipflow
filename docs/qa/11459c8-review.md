# QA review · 11459c8 · 093 hashtags = exact ORDER at the end; rules key `required_in_order` (P0)

Reviewer: Lane C · 2026-10-02

All three rules files renamed `required_prefix` → `required_in_order` with the new wording + `"position": "end"`;
`campaigns.hashtags()` reads the new key and falls back to the old one. No `required_prefix` / "first in the
caption" left on main or lane-b (`git grep`).

## Re-check (fresh import, ime-roleplay job 4590c193, candidate af550230)
Generated description ends with `#imeroleplay #imestrong #imeMKLIP2 #motionklip #ezklip`: exactly the 5 required
tags, in order, nothing else, at the end. PASS.

## Findings
- None.
