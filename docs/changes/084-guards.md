# 084 · Guards: hook window settings, API job language default, rank parsing (QA #4, #5, #9) · main.py, worker.py

- **Hook windows (QA #4).** `transcript_windows()` never advanced when overlap ≥ window (infinite loop).
  `PUT /api/settings` now rejects a change that would leave `HOOKS_WINDOW_OVERLAP_MINUTES` < 0 or ≥
  `HOOKS_WINDOW_MINUTES` (or a window < 1 min / non-numeric), checked against the values the PUT would
  leave effective (empty = unset → env → default). The worker clamps too (window ≥ 60 s; invalid overlap →
  half the window, negative → 0) and logs it, for values set via env/DB directly.
- **Job language (QA #5).** `POST /api/jobs` without `language` (API callers) uses the `WHISPER_LANGUAGE`
  setting (if auto/en/id, else `id`), as before 079. The UI still sends an explicit choice.
- **Rank step (QA #9).** Negative ids are rejected (`candidates[-1]` silently picked the last one); a
  non-numeric score skips that item with a log line instead of failing the job; the fill-by-score
  fallback covers the gap.

**Verified** on the stack: PUTs with overlap 30/30, window 2/overlap 2, overlap −1, overlap "abc" → 400;
clearing the window key → 200. Worker clamp logged for 1800/1800 and −5. Fake-provider run of
`select_hooks()` (5 windows + rank returning id −1, score "high", one valid) → both skipped and logged,
job completes with 2 clips. `POST /api/jobs` without language passes validation (stopped by an unknown
campaign; no job created).
