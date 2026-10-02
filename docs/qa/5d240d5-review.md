# QA review · 5d240d5 · 077 hook analysis over the whole transcript

Reviewer: Lane C · 2026-10-02 · reviewed against committed HEAD

Invariants checked: every AI call via `ai_router.ai_generate_json` (OK) · providers return
`(data, model, usage)` at every return site (claude.py:183, gemini.py:54, OK) · `check_cancelled()`
before each call and `except JobCancelled: raise` before the per-window catch (OK) · AI errors
(`AIError`, not `RuntimeError`) still propagate to `record_failure` instead of being swallowed
per window (OK) · new settings only in `DEFAULT_SETTINGS` (OK) · `hook_provider` still set
(`parse_hooks` → `"provider"`, `worker.py:1948`).

## Findings (most severe first)

1. **Medium · infinite loop on bad settings.** `transcript_windows()` (`worker/worker.py:2012`)
   advances `start = stop - overlap_s` (`:2024`). If `HOOKS_WINDOW_OVERLAP_MINUTES >=
   HOOKS_WINDOW_MINUTES` (or window = 0), `start` never advances and the worker hangs in analysis,
   heartbeating, with the list growing until OOM. Only reachable for transcripts over
   `HOOKS_FULL_TRANSCRIPT_MAX_CHARS` (400k), but the values are editable in Settings with no
   cross-validation. Suggest clamp overlap < window, window ≥ 1.
2. **Low · negative rank ids accepted.** `candidates[int(item["id"])]` (`:2162`): id `-1` silently
   selects the last candidate (Python negative index) instead of being rejected.
3. **Low · non-numeric rank score fails the job.** `int(item.get("score", ...))` (`:2167`) sits
   outside the try; a score like `"high"` raises `ValueError` and fails the whole analysis.
4. **Low · rank-step provider not recorded.** Hooks keep the *window* call's provider in
   `hook_provider`; if the rank call failed over to the other provider, that isn't visible.
5. **Info · cost.** Default 400k chars ≈ 100–130k input tokens per analysis on one call; the token
   log line makes it observable. No budget cap.

## Not verified
- Windowed path was not exercised live (needs a >400k-char transcript). Code-read only.
- Ranking quality vs the old 24k-char cut (eval scripts `scripts/eval_hooks*.py` are untracked in
  Lane A's tree; not run by QA).
