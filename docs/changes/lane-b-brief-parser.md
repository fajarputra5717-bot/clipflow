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
