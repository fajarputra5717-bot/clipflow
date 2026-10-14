# groq-provider 72c7025 (220, Groq as second AI provider) — code + fake-Groq harness + mocked UI; NO live Groq call

Tested from `git archive origin/groq-provider`: unit tests, a local fake Groq server (the real `shared/ai/groq.py` pointed at it via `groq.API_URL`, stub Gemini/Claude modules, the real router, fake key `gsk_FAKE_…`), and the mocked UI. I did **not** make real Groq calls: that needs GROQ_API_KEY from the production `/opt/clipflow/.env`, which a peer cannot authorise for me (see "Needs your decision").

## Verified
1. **Unit tests:** tests/test_ai_groq.py 9 OK, tests/test_ai_router.py 14 OK, tests/ui/specs/ai-status.spec.js (+ my screenshot spec) 8/8 passed on desktop + mobile projects.
2. **Order and policy** (router harness): auto order Gemini → Groq → Claude. Gemini transient ×2 (AUTO_ATTEMPTS_PER_PROVIDER) → Groq served; Gemini *permanent* error stops at once (Groq 0 calls, Claude 0). Backoff = 2^(n−1) + uniform(0,1) s (measured 1.68 s for attempt 1), capped at 20. An invalid policy value (`xyz`) logs and falls back to auto. Groq `400 json_validate_failed` → transient (retried twice, then Claude); any other Groq 400/404 → skip to the next provider.
3. **429 / 413:** Groq 429 with `retry-after: 7` → next provider, exactly 1 Groq call (no retries), Groq's breaker failure count stays 0, Groq paused 7.0 s: a second call inside the pause makes 0 Groq calls. 413 "Limit 8000, Requested 9000" → next provider, no pause, limit learned (8000) and the next ~10k-token prompt is skipped up front ("AI: skipping groq … ~10001 prompt tokens > 8000"). Forced `groq` + 429 and forced `groq` + 413 → "using the auto chain without it", served by Gemini. With Groq as the only provider: 429 → AITransientError, 413 → AIPermanentError.
4. **Up-front skips:** an image call (`edit_moments` with images) makes 0 Groq calls ("no vision model"); an over-limit prompt makes 0 calls.
5. **Per-provider breaker:** state is per name (`_failures[name]`, `_open_until[name]`); groq's failure count resets after opening; verified by reading the code and the harness (I could not isolate one provider in a clean run: all stubs were failing).
6. **Key hygiene:** `GROQ_API_KEY` is only in `ENV_ONLY_KEYS`, not in `DEFAULT_SETTINGS`, so `GET /api/settings` never lists it and a PUT with it is an unknown key (400, as since 198). A 401 → "Groq refused the API key (401)" with the key in no log line or error; the key is sent only as `Authorization: Bearer` (never in the request body). Settings save: `CLIP_ANALYSIS_PROVIDER` / `TEXT_UTILITY_PROVIDER` other than auto|gemini|groq|claude → 400 (main.py, case-insensitive, trimmed, stored lower-case). `GET /api/ai/status` is filtered by the caller's `user_id` for "last hooks" and exposes only provider names/configured flags.
7. **UI:** Settings → AI & transcription "Provider order (auto) Gemini → Groq → Claude (no key) · Your latest hooks: Groq · 14 Oct, 14:40 WIB": 668×65 px at 1440 and 338×73 at 390, no overflow, text colours correct in light (rgb 29,29,31) and dark (245,245,247) once the app's `data-theme` is set.

## Findings
- **Low:** the key is not redacted from upstream text. If a Groq error body ever echoed the key (Groq doesn't today), `_error_message()` would carry it into the router log and the stored job error (my fake server did exactly that: key present in the logs for a 500 and a 400). Cheap fix: replace the configured key with `***` in `generate_json`'s message before raising.
- **Low (note):** a forced provider that skips falls back to the auto chain silently for the user (only a log line); `hook_provider` records who really answered, so the Settings row stays truthful.

## Needs your decision
The live checks (real Groq responses, strict-schema output, the `hook_provider = groq` row written by a real job, grep of real worker logs after a real 401) need GROQ_API_KEY from `/opt/clipflow/.env` (production secrets). Lane A suggested copying it for a throwaway worker image; I will not read that file without your typed approval. 

## Not verified
Real Groq behaviour (limits, strict-schema acceptance of the prompts' schemas), forced Gemini (503 for over an hour per Lane A), a full job through Groq, `hook_provider` end to end.

Merge: OK for the router, provider, settings and UI as tested; the live Groq run is still open.
