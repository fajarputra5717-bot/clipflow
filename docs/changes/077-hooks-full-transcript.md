# 077 · Hook analysis sees the whole transcript · worker.py, shared/ai/*, shared/settings.py

**Problem.** `analyze_hooks()` cut the timed transcript to its first 24,000 characters. On job
1522410e (75 min, 65,588 chars) the prompt saw only the first 32 min (42 %); every clip of the three
jobs before this change started within the first 31 min.

**Change.**
- `build_hooks_prompt()` (prompt text unchanged, byte-identical apart from the removed cut) and
  `parse_hooks()` split out of `analyze_hooks()`; `select_hooks(segments, platform, clip_count,
  durations, call)` decides the input:
  - timed transcript ≤ `HOOKS_FULL_TRANSCRIPT_MAX_CHARS` (400,000, setting) → one call, whole video;
  - above → `transcript_windows()` of `HOOKS_WINDOW_MINUTES` (30) with `HOOKS_WINDOW_OVERLAP_MINUTES`
    (2) overlap, max(N, 3) candidates per window, `dedupe_hooks()` (>50 % of the shorter clip = same
    moment, higher score wins), then one ranking call (`build_rank_prompt`, `HOOK_RANK_SCHEMA`) that
    returns candidate **ids** (timestamps can't be invented); a short answer is filled by score.
  - `call` is the only provider-specific part: production = `router_hooks_call` (router policy,
    failover); the TASKS-5 eval passes a forced-provider call through the same code.
- Providers return `(data, model, usage)`; the router adds `usage` {input, output (incl. thinking)}
  to `meta`. Every hook call logs `Hooks call <full|window i/n|rank>: <chars> chars → provider (model),
  tokens in/out`.
- Real transcripts here are ~550 chars/min (2.5 h ≈ 85k chars), so the windowed path is for very long
  streams only.

**Verified.** Stub test: 75 min → 1 call; 3 h / 586k chars → 7 windows + rank, picks spread across the
video. Production router on 1f9e8062 (128 min, 72k chars): 1 call, picks at 30.4 min and 59.0 min
(before: 16.8 and 30.1). Gemini returned 503 twice → failover to Claude, logged with 42,835 input tokens.
