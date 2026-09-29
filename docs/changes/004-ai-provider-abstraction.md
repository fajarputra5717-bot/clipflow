# 004 — AI provider abstraction, no behaviour change (R-20)
Date: 2026-09-29 · Commit: see `git log --grep R-20` · Files: shared/errors.py, shared/ai/*, main.py, worker.py, CLAUDE.md

## What changed
- `shared/errors.py`: `AITransientError` / `AIPermanentError` (+ `AINotConfiguredError`), `classify_exception()`,
  `is_transient_gemini_error()` (the baseline's retry markers, verbatim).
- `shared/ai/router.py`: `ai_generate_json(prompt, schema, *, task, max_tokens)`; `configure(setting, log)` once per process.
  `shared/ai/gemini.py`: one Gemini attempt, raises typed errors only. `shared/ai/claude.py`: stub for R-21.
- All 4 call sites go through it: worker `analyze_hooks` (task `hooks`), main.py `new_hook` (`new_hook`),
  `fix_subtitle_ai` (`subtitle_fix`), `generate_description` (`description`). `gemini_call()` and
  `gemini_generate_json()` are gone; each call site now declares a JSON Schema (`HOOKS_SCHEMA`, `NEW_HOOK_SCHEMA`, …).

## Why
Two wrappers with different retry/error handling, and string-matched errors. R-21/R-22 need one typed interface.

## Decisions & trade-offs
- Kept behaviour identical: same prompts, same model setting, Gemini request still only
  `response_mime_type=application/json` (schema and max_tokens are NOT sent to Gemini: that would change output).
  Worker retries exactly as before (`GEMINI_MAX_ATTEMPTS`, same markers, same 2^n + jitter); backend passes
  `attempts=1` because it never retried. Error text in `jobs.error_message` / HTTP detail is still `str(exc)`.
- Missing key in the backend still returns 503 "GEMINI_API_KEY is not configured".
- `validate_gemini()` unchanged (R-22 / TASKS-5 T5 revisit it).

## Gotchas for future changes
- google-genai 2.x closes a `Client` when it's garbage-collected: `genai.Client(...).models.generate_content(...)`
  chained on a temporary fails with "client has been closed". Hold the client in a variable (found while testing this).
- New AI call → `ai_router.ai_generate_json(...)` with a `task` name and schema. Never import an SDK in main/worker.

## What I did NOT verify
- Byte-identical output on a real input: Gemini returned 503 "high demand" during testing, so no successful
  live response was compared. Request construction is unchanged by inspection; retry/classification tested offline
  and the live 503 was classified `AITransientError` with the correct retry log line.
