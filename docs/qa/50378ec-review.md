# QA review · 50378ec · docs: roadmap P0–P5 + Fandra payout corrected

Reviewer: Lane C · 2026-10-02 · docs only

`docs/roadmap.md` defines the phases and the Lane C gate (a phase starts only after QA signs off the previous
one; any open High blocks). The P0 row is QA's P0 gate checklist: Submagic-final loudness (+ failure → keep
final + UI warning, ~2× disk reserve, previews single-pass), unresolvable campaign watermark → failing chip,
hashtags at the end in exact order (rules wording), min analysis window 10 min, watermark Y min 16 %,
`WHISPER_LANGUAGE` relabelled, badge bump. These map 1:1 to open QA items (summary #1–#4), so the P0 gate
re-checks each.

No findings. Note: P4's "progress bar" is an in-video effect, not UI progress (the island rule doesn't apply).
