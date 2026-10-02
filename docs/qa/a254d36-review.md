# QA review · a254d36 · 115 campaign clips get their description at analysis (ends with the hashtags)
Reviewer: Lane C · 2026-10-03 · `campaign_description()` runs at preview build for campaign clips with an EMPTY
description, same prompt as "Generate description" (moved to `shared/descriptions.py`), never overwrites, never fatal,
`JobCancelled` re-raised. Live (P1 gate): all 4 fresh campaign clips had descriptions ending with their exact hashtags.
Not verified: non-campaign "Generate description" prompt byte-identical after the move (code moved, not diffed).
