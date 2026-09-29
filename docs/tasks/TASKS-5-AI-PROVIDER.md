# ClipFlow — stream: AI PROVIDER ABSTRACTION

Segmented task stream. Companion streams: `TASKS-4-VIDEO.md`,
`TASKS-4-UIUX.md`, `TASKS-4-SECURITY.md`.

Read `CLAUDE.md` and `docs/changes/INDEX.md` first. Grep for function
names; don't trust line numbers.

Ground rules unchanged: one task = one commit, `docs/changes/NNN-<slug>.md`
+ INDEX line, settings via `DEFAULT_SETTINGS`, compile checks, honest
"what I did NOT verify" notes.

---

## Why

Gemini 3.6 Flash is returning `503 high demand` often enough to fail
jobs. `GEMINI_MAX_ATTEMPTS` retry already exists and isn't enough —
persistent upstream capacity problems don't resolve on backoff.

The fix is provider-agnostic AI calls with failover, not swapping one
hardcoded vendor for another. Single-vendor dependency is the actual
defect; Gemini being down today is just how it surfaced.

---

## Task 1 — Provider abstraction (no behaviour change)

Pure refactor. Gemini stays the only provider and the default. Nothing
about output should change. **Commit this separately** so that if hook
quality shifts later, git bisect can tell you whether the refactor or
the new provider caused it.

Current AI call sites (grep to confirm — there may be more):

- `worker.py`: `analyze_hooks()`, wrapped by `gemini_call()`,
  plus `validate_gemini()` at startup
- `main.py`: `gemini_generate_json()` helper, `new_hook()`,
  `fix_subtitle_ai()`, `generate_description()`

Two separate wrapper helpers currently exist (`gemini_call` in the
worker, `gemini_generate_json` in the backend) and they don't share
retry or error handling. Unify them.

Define one interface both providers implement:

```
ai_generate_json(prompt, schema, *, task, max_tokens) -> dict
```

- `task` names the call site (`"hooks"`, `"subtitle_fix"`,
  `"description"`) so per-task model choice and logging are possible.
- `schema` is a JSON Schema describing the expected shape. Gemini's
  path can keep using its existing response-format handling; the schema
  matters most for the Claude path (see Task 2).
- Raises a typed `AITransientError` (429/503/5xx/timeout) vs
  `AIPermanentError` (400/401/malformed) — the retry and failover logic
  in Task 3 depends on that distinction, and the current code doesn't
  make it.

**Acceptance:** all call sites go through the new interface, output is
byte-identical to before on the same input, Gemini remains default.

---

## Task 2 — Claude provider

Add `anthropic` to `requirements.txt` for both images.

- Endpoint is the Messages API (`client.messages.create`).
- **Use tool-use for structured output, not "respond only with JSON"
  prompting.** Define the expected shape as a tool `input_schema` and
  force it with `tool_choice={"type": "tool", "name": "..."}`. The
  model is then constrained to the schema, which is materially more
  reliable than parsing JSON out of prose. This matters most for
  `analyze_hooks`, whose output feeds straight into DB inserts.

Sketch for the hooks call:

```python
resp = client.messages.create(
    model=model,
    max_tokens=4096,
    tools=[{
        "name": "emit_clips",
        "description": "Return the selected viral clip candidates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "clips": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "start":        {"type": "number"},
                            "end":          {"type": "number"},
                            "title":        {"type": "string"},
                            "reason":       {"type": "string"},
                            "content_type": {"type": "string",
                                             "enum": [...CONTENT_TYPES...]},
                            "rating":       {"type": "integer"},
                        },
                        "required": ["start", "end", "title", "reason",
                                     "content_type", "rating"],
                    },
                },
            },
            "required": ["clips"],
        },
    }],
    tool_choice={"type": "tool", "name": "emit_clips"},
    messages=[{"role": "user", "content": prompt}],
)
```

Read the result out of the `tool_use` content block's `input`.

**Model choice — per task, not one global setting:**

- `hooks` → **Sonnet 5**. This is the product differentiator and your
  volume is low (a couple of clips per job, a few jobs a day), so cost
  is close to irrelevant and quality should win.
- `subtitle_fix`, `description` → **Haiku 4.5**. Mechanical, cheap,
  high-frequency.

Settings: `CLAUDE_API_KEY` (add to `SECRET_SETTING_KEYS`),
`CLAUDE_MODEL_HOOKS`, `CLAUDE_MODEL_UTILITY`.

**Verify current model IDs and pricing against Anthropic's docs at
implementation time** rather than trusting the values written here —
model lineups move. Do not hardcode a model ID in more than one place.

---

## Task 3 — Failover and retry policy

- Per-task provider preference: `AI_PROVIDER_HOOKS`,
  `AI_PROVIDER_UTILITY` — `gemini` | `claude` | `auto`.
- `auto` = try preferred, fall back to the other on `AITransientError`
  only. Never fail over on `AIPermanentError` — a malformed prompt
  fails identically on both providers and burning a second vendor's
  quota on it is pure waste.
- Exponential backoff **with jitter** and a ceiling, per provider.
- Log every failover with provider, task, error class, and attempt
  count. Record which provider actually produced each result — store it
  on the candidate row, so the Task 4 evaluation and the phase-2
  performance feedback loop can correlate hook quality by provider.
- Circuit breaker: after N consecutive transient failures, stop calling
  that provider for a cooldown window instead of retrying every job.

---

## Task 4 — Prompt evaluation (do not skip)

**The prompts are tuned for Gemini. They will not necessarily perform
identically on Claude.** Hook selection is the thing your whole channel
strategy rests on — a silent quality regression here is worse than a
503, because a 503 is visible and a worse hook is not.

- Take 5–10 real transcripts already processed. Run each through both
  providers with the same prompt. Put the outputs side by side in
  `docs/changes/` and compare: do the clips land on genuinely strong
  moments, are timings sane, is `content_type` used correctly, are the
  Indonesian titles idiomatic?
- Expect to need provider-specific prompt variants. Claude generally
  prefers explicit structure and stated criteria over terse
  instructions. Keep both variants; select by provider.
- **Report honestly which provider produced better hooks**, including
  "too close to call on this sample" — that's a legitimate finding.
  Don't manufacture a winner.
- If Claude is clearly better, say so and recommend flipping the
  default. If it's clearly worse, keep Gemini preferred and use Claude
  purely as 503 insurance.

---

## Task 5 — Settings UI

- New `AI` settings group covering both providers: keys, per-task
  model, per-task provider preference.
- Show which provider is currently healthy (last success/failure and
  whether a circuit breaker is open). When a job's hooks came from the
  fallback provider, say so on the candidate — otherwise a quality
  difference is invisible and unattributable.
- `validate_gemini()` at worker startup currently hard-fails if the
  Gemini key is missing. That becomes wrong once Claude is an option —
  it should fail only if **no** usable provider is configured.

---

## Order

1 (abstraction) → 2 (Claude provider) → 3 (failover) → 4 (evaluation)
→ 5 (UI).

Task 1 alone fixes nothing user-visible — resist the urge to fold it
into Task 2. The separation is what lets you attribute a later quality
change to the right cause.
