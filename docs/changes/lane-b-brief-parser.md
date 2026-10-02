# Brief parser (lane B, task 5) — number assigned by Lane A at merge

New `shared/brief_parser.py`: `parse_brief(text, today=, slug=)` / `parse_brief_file(<slug>.md)` →
rules dict in the docs/campaigns schema + `unsure: [{field, why}]`. Deterministic (patterns for
the MotionKlip-style Indonesian template), no AI: repeatable and exactly testable; anything the
text doesn't settle goes to `unsure`, never guessed.

Extracts: name, category, platforms, payout (`fixed_threshold` / `per_block` / `unknown`, read by
`payouts.model_from_rules`), CPM, min/max views, payment methods, claim form, Discord tag
(manual_only), monthly per-account limit, budget + refills, WIB weeks, period, source channels
(Bahan Clip), hashtags in order, socials (brand vs creator), watermark (required, template,
placement guide), title examples, content rules (11 known ids; unknown rule lines → unsure).

Saved briefs: IME and Fandra reproduce the hand-made rules files (same payout model, platforms,
hashtag order, content-rule ids, weeks, sources, period). The unsure list matches the questions
that needed the admin (IME: account unit, carry-over, Oct 29–31, period elsewhere, sources;
Fandra: rounding, total budget, year). MotionKlip's brief is still pending → all unsure.
Tests: `tests/test_brief_parser.py` (6).

## AI fallback (2026-10-02)

Regex stays primary. `parse_brief(..., ai=router_ai())` calls the utility model (router task
"brief") only when the patterns leave a gap: no payout rate, no platforms, no hashtags, no content
rules, or unrecognised rule lines (`ai_reasons`). The answer fills ONLY missing fields; each filled
field is listed in `ai_derived` and in `unsure` with `source: "ai"` (it replaces the pattern's
"not found" note for that field) so the Campaign screen asks for confirmation. AI content rules
carry `ai: true`. An AI failure adds an `unsure` note and keeps the pattern result. IME/Fandra/
MotionKlip never trigger it. Also: English patterns for "no watermark" and deadlines ("Submit
views by Oct 31, 2026"), currency from `$`/`Rp`/`€` in the text, and `payouts.model_from_rules`
returns Unknown for non-IDR payouts (they used to be truncated to ints).

Live run on `tests/fixtures/briefs/english-cpm-sample.txt` (`scripts/brief_ai_check.py`, one call):
platforms, CPM $1.50 per 1,000 with a $300/clip cap, $6,000 budget, @mention, 20–60 s, both
source channels and 3 content rules filled and all marked AI-derived; hashtags, deadline and the
watermark ban came from patterns. Missed by the model: "at least 10,000 views" (min views) and
the burned-in-captions requirement (no field for it yet). Tests: 5 new (fake AI).

## Schema: min_views_to_qualify + requirements; English patterns (2026-10-02)

- `min_views_to_qualify` (int): "at least 10,000 views", "views must reach 10k", "Minimal Views …",
  "target 40.000 Views". Feeds payout `min_views` when the payout has none.
- `requirements: [{id, text}]` (rule chips): obligations (must / required / wajib / harus). Known ids:
  burned_in_captions, vertical_9_16, language_english, language_indonesian, credit_creator; other
  obligation lines are kept verbatim as `custom_…`. Prohibitions stay content rules (a line can
  now carry several, e.g. insults + politics); unknown prohibitions → unsure + AI.
- English patterns: `$`/`€`/`£` "X per 1,000 views" / "X CPM" → `model: cpm` (native, see payouts),
  per-clip cap, counted-views cap, budget; multi-platform lines; "Tag @x"; "Only clip from
  youtube.com/@…" sources; length "20 to 60 seconds" / "max 60 seconds"; currency words
  (dollars/euros/rupiah).
- AI fallback: `min_views_to_qualify` and `requirements` (each AI chip `ai: true` + unsure). The
  prompt now spells out the exact output keys: the Gemini provider does not send the schema, so it
  invented keys and dropped `requirements`/`currency`.

Live (`scripts/brief_ai_check.py`): the English CPM sample is now fully covered by patterns (no AI
call). The new prose sample (`tests/fixtures/briefs/english-prose-sample.txt`, numbers in words, no
bullets) via the AI, 2 runs: both cpm $2.50 USD, min 5,000, $250 cap, requirements
[burned_in_captions, credit_creator], 3 content rules, deadline 2026-11-30, all marked unsure.
Platforms differed between runs ("Meta's apps or the ByteDance one" is ambiguous): confirm in UI.
