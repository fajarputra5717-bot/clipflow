# 005 — Claude provider (R-21)
Date: 2026-09-29 · Commit: see `git log --grep R-21` · Files: shared/ai/claude.py, shared/ai/router.py, shared/settings.py, worker.py, .env.example

## What changed
- `shared/ai/claude.py`: Messages API via the `anthropic` SDK (already in both requirements). Structured output =
  a strict tool (`emit_result`) whose `input_schema` is the call site's schema (+ `additionalProperties:false`);
  array schemas (hooks) are wrapped as `{"clips":[...]}` and unwrapped. Raises typed errors only; SDK retries off.
- Router has a provider registry (`provider=` kwarg, default still `gemini`, so no job uses Claude yet; R-22 wires the policy).
- Settings: `ANTHROPIC_API_KEY` (secret), `CLAUDE_MODEL_ANALYSIS=claude-sonnet-5-5` (tasks hooks/new_hook),
  `CLAUDE_MODEL_UTILITY=claude-haiku-4-5` (subtitle_fix/description). Model IDs only in `DEFAULT_SETTINGS`.
- Worker hooks call: `max_tokens` 4096 → 16000 (Claude's adaptive thinking counts against it; Gemini ignores it).

## Decisions & trade-offs
- **Model IDs checked against Anthropic's model list (2026-09-25 cache):** REBUILD said `claude-sonnet-5`; the current
  Sonnet is `claude-sonnet-5-5` at the same price ($2/$10 per MTok), so defaulted to it. Haiku: alias `claude-haiku-4-5`
  (= `claude-haiku-4-5-20251001`).
- **Forced tool use is not universal any more:** Sonnet 5.5 / Opus 5.5 / Fable 5.1 return 400 on
  `tool_choice {"type":"tool"}`. The provider forces the tool where accepted (Haiku 4.5, Sonnet 5) and otherwise sends
  `auto` + "call emit_result exactly once" + `strict:true` (schema still guaranteed). The first 400 per model is
  remembered per process, costing one failed (unbilled) request. No tool call under `auto` → `AITransientError` (retry fixes it).
- `stop_reason` `refusal` / `max_tokens` → `AIPermanentError`. Server-side refusal fallback (beta
  `server-side-fallback-2026-07-01`, `fallbacks:"default"`) is sent for the models that accept it.
- Same prompts as Gemini (TASKS-5 T4 prompt evaluation is still TODO).

## What I verified
Live, in the worker container: hooks on a 12-segment Indonesian transcript via Sonnet 5.5 (6.7 s, 2 valid clips, sane
timings, idiomatic titles, forced→auto fallback triggered as expected), description via Haiku 4.5 with forced tool (7.8 s).

## What I did NOT verify
- `subtitle_fix` / `new_hook` through Claude end-to-end (same code path, different schema).
- Behaviour on a real 429/529 from Anthropic (classification by status code, tested offline only).
