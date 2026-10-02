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
