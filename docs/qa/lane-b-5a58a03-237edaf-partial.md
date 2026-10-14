# lane-b 5a58a03..237edaf (Review / Editor / Sound effects polish) — PARTIAL: mocked UI + code, live parts pending

Tested from `git archive 237edaf` served on 127.0.0.1:8091 (mocked /api) plus code reading. Staging does not run these commits yet (it has aa9aee0/d013824), so the live parts below are not verified.

## Verified now
- Mocked Playwright (touched specs review, rules, editor, sfx; desktop 1280×900 + mobile 390×844 projects, 1 worker): **120 passed, 2 skipped, 0 failed** (sfx.spec showed no flake in my single run). Unit tests: test_review_state (7), test_rule_checks_editor (6), test_keyword_stopwords (3) OK.
- `shared/review_state.finished_label` (5a58a03), evaluated at 05:30 WIB: completed clip with no post "Approved · Not scheduled yet"; rendering "Approved · Rendering final"; review status → None; planned in 3 h / 40 h / 9 days → "Scheduled Thu 08:30" / "Fri 21:30" / "Sat 24 Oct 05:30" (WIB, date added after a week); planned in the past "… (overdue)"; planned without a date → Not scheduled yet; posted → "Posted on YouTube"; posted on 2 platforms + a planned one → "Posted on 2 platforms · next Thu 10:30"; dropped rows ignored. The posts query is filtered by `user_id` (no cross-user leak).
- Review rendering (c03230b, 1d31008, 5a58a03): every user/AI text goes through `esc()` (rule text, transcript quote, reason, finished label, chip titles), so a hostile quote cannot inject markup; failing chips only, otherwise one "✓ All rules pass" whose title lists the rules.
- Keyword stopwords (10bfa9d): 366 words (id + en + fillers) feed both the editor chips and the worker's AI pick (`worker.py` line swapped to `languages.keyword_stopwords()`); a few ordinary words are now never offered (`bang`, `tak`, `mas`, `bro`, `guys`, `mo`, `tu`, `oh`).

## Findings
- Low: "Posted on facebook" (lower-case): `PLATFORM_NAMES` in `shared/review_state.py` has TikTok/Instagram/YouTube but not Facebook, which the app supports since P5; add `"facebook": "Facebook"`.
- Low (note): the stoplist applies to every clip language, so an English-only clip loses the Indonesian filler/particle words too (harmless), and `bang` is also an English gaming word.

## Waiting for the restage (live checks I will do)
Finished labels on real clips (approved + scheduled/posted), the content-check issues list from a real backend `rule_checks`, grouping by source video across two real jobs, keyword chips + the worker's auto-pick on a fresh import, phone editor scroll-margin on a real clip, the sound-effects sheet licences/`Use for…` on real data, and the 360–1440 editor tab sweep.

Merge: not yet (live parts pending); no blocker found so far.
