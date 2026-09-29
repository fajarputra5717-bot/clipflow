# 006 — AI failover policy (R-22)
Date: 2026-09-29 · Commit: see `git log --grep R-22` · Files: shared/ai/router.py, shared/settings.py, main.py, worker.py, CLAUDE.md

## What changed
- `CLIP_ANALYSIS_PROVIDER` (hooks, new_hook) / `TEXT_UTILITY_PROVIDER` (subtitle_fix, description) ∈ `gemini|claude|auto`,
  both default **auto** = Gemini first, Claude on `AITransientError` only. Providers without a key are skipped.
- Retries with exponential backoff + jitter, ceiling 20 s. Single provider: `GEMINI_MAX_ATTEMPTS` (now applies to either
  provider). auto: 2 attempts per provider, then fail over. Backend handlers: 1 attempt per provider (no sleeping in a request).
- Circuit breaker per provider, per process: 3 consecutive transient failures → skipped for 60 s. If every candidate is
  open, the one closest to reopening is still tried (half-open) rather than failing with no call.
- Every retry / failover / breaker-open / permanent error is logged as `AI: ...` with provider, task, error class,
  status and attempt count.
- `clip_candidates.hook_provider` (ensure_schema) set by worker hook analysis and by `new_hook`.
- `validate_gemini()` → `validate_ai()`: worker fails only if **no** provider has a key (TASKS-5 T5 bullet, needed now
  that auto is the default). Startup log prints the policy and `provider_health()`. Job message "Gemini 3.6 Flash
  analysing viral hooks" → "AI analysing viral hooks".
- `new_hook` max_tokens 1024 → 8000 (Sonnet 5.5 thinks before answering).

## Decisions & trade-offs
- Never fail over on `AIPermanentError`: a malformed prompt fails identically on both vendors.
- In single-provider mode the breaker can end retries early (3rd failure opens it) but never blocks the only provider.
- Breaker state is in memory: backend and worker each keep their own, reset on restart. Good enough for one worker.
- Both policies default to auto (the user asked for CLIP_ANALYSIS_PROVIDER=auto; utility follows for the same reason).

## Gotchas for future changes
- New AI task name → add it to `TASK_PROVIDER_SETTING` (router) and `_MODEL_SETTING` (claude.py) or it runs as a utility task.
- No UI yet for these settings or for `hook_provider` (TASKS-5 T5, TODO). Change them via PUT /api/settings or .env.

## End-to-end run (2026-09-29, job 0316327c…, youtube VgwaVaLaOVQ, 136 s)
- download → normalize → whisper → hooks → review → regenerate-preview → approve → final: all passed.
- Hooks: Gemini 503 "high demand" twice → `AI: FAILOVER task=hooks gemini -> claude after 2 attempt(s)` →
  served by `claude-sonnet-5-5`; both candidates have `hook_provider=claude`. Versions logged: "Applied changes",
  "Final render requested".
- Final: h264 1080x1920 + aac, 34.5 s. Frames at 4/12/24 s inspected: watermark present, ClipFlow's burned subtitle
  present (small, under the source's own hardcoded caption).

## What I did NOT verify
- Hook *quality*: the test video is a Spanish-audio meme with fake Indonesian captions, so Whisper (WHISPER_LANGUAGE=id)
  produced a nonsense transcript and the hooks were picked from it. Needs a real Indonesian-speech video (TASKS-5 T4).
- Seen but not investigated (pre-existing render path, not this change): bottom facecam panel half black on a source
  with no facecam; burned subtitle looks small at size 42; non-Latin glyphs from the bad transcript render as boxes/Cyrillic.
- A real Anthropic 429/529, and the breaker opening in production (tested offline only).
