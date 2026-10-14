# 220 — Groq as the second AI provider (auto chain Gemini → Groq → Claude)

Owner request 2026-10-14 (confirmed).

## Provider (shared/ai/groq.py)
- Groq's OpenAI-compatible Chat Completions over `requests` (no new dependency). One attempt per call; retries and
  failover stay in the router. Raises only shared.errors types.
- Models (console.groq.com/docs/models, 2026-10-14, production): `GROQ_MODEL_ANALYSIS` = `openai/gpt-oss-120b`
  (hooks, new_hook, brief), `GROQ_MODEL_UTILITY` = `openai/gpt-oss-20b` (everything else). Both: 131,072-token
  context, 65,536 max completion, strict structured output, `reasoning_effort` medium (analysis) / low (utility);
  completion budget = the caller's max_tokens + 4,096 / 1,024 for reasoning.
- Structured output: `response_format` json_schema with `strict: true`. Strict mode needs every object closed and every
  property required, so optional properties become nullable + required and their nulls are dropped from the answer;
  a top-level array (hooks) is wrapped as `{"clips": [...]}` and unwrapped: callers get the same shape as from
  Gemini/Claude. Models outside the strict list fall back to JSON mode + the schema in the prompt.
- `GROQ_API_KEY`: env-only (`ENV_ONLY_KEYS`, never the DB or the Settings UI), sent only as the Bearer header; error
  messages never contain it. Empty entry in `.env.example`.
- Limits: the per-minute token limit (free plan: 8K on gpt-oss, 30 RPM, 200K/day) also caps a single request. It is
  learned per model from `x-ratelimit-limit-tokens` (and a 413's "Limit N"); `accepts()` estimates chars / 3 tokens
  + the completion budget and says no up front when that's over min(context, learned limit). No vision: calls with
  images skip Groq.

## Router (shared/ai/router.py)
- `AUTO_ORDER` = gemini → groq → claude for CLIP_ANALYSIS_PROVIDER and TEXT_UTILITY_PROVIDER; "groq" is also a forced
  value (settings save validates auto|gemini|groq|claude). hook_provider records "groq" (meta provider name).
- Unchanged: fail over on transient errors only, exponential backoff + jitter, circuit breaker per provider,
  permanent errors stop at once.
- New `AIProviderSkip` (shared/errors.py): Groq 429 (rate limit), 413 (request too large) and requests only Groq
  rejects (400 schema/model, 404 model) → no retries and no breaker failure; a 429's retry-after leaves Groq alone
  that long (`breaker.pause`, ≤ 1 h); the next provider is tried. If no provider is left: 429 → transient (the job
  retries later), 413 → permanent. A refused Groq key (401/403) = not configured → next provider in auto.
- Up front: providers with `accepts()` (Groq) are dropped from the chain for a call they can't take (log
  "skipping groq … up front"). A forced provider that can't take the call → the auto chain without it (logged).

## UI
Settings → AI & transcription: first row "Provider order (auto): Gemini → Groq → Claude" ("(no key)" when missing),
any forced provider, and "Your latest hooks: <provider> · <time> WIB" (`GET /api/ai/status`, the caller's own jobs).
The two provider settings and the Groq/Claude model settings are now listed in that group.

## Tests
tests/test_ai_groq.py (request shape, strict schema conversion, nulls, every error class, key never in URL/body/errors,
accepts + learned limit), tests/test_ai_router.py (order, failover, 429/413 skip, pause, no breaker count, up-front
skip with the real Groq module, images, forced groq, refused key, permanent stop, per-provider breaker),
tests/ui/specs/ai-status.spec.js. Live checks on staging: see the report (needs GROQ_API_KEY in .env / .env.staging).
