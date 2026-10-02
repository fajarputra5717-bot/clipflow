# QA review · 1d5f4a7 · 110 hook score stored and shown as "AI estimate" (P1)
Reviewer: Lane C · 2026-10-02 · `clip_candidates.score` now written at analysis (was always NULL: every
`ORDER BY score` sorted NULLs); "new hook" clears it; UI chip "AI estimate N" + reason. No prompt change (frozen
wording OK). Findings: **Low** · the card also keeps the old "★ n/10" rating overlay on the player, so two scores
are visible (mock shows one: "Hook 94" / "Virality 94"). Consider dropping the ★ rating or labelling it.
