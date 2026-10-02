# QA review · 6baff13 · 094 hook analysis window minimum 10 minutes (P0)

Reviewer: Lane C · 2026-10-02 · deployed backend + worker confirmed

Settings PUT rejects windows < 10 min (400, clear message); worker clamps to 600 s with a log line. Ran the
committed `transcript_windows()` on a 2 h transcript: (60 s, 0) → 600 s, 12 windows · (300 s, 120 s) → 600 s, 15 ·
(1800 s, 120 s) → 5 · (600 s, 900 s) → overlap halved to 300 s, 23. PASS.

## Findings
- None. (Settings PUT path code-read, not exercised over HTTP to avoid writing settings.)
