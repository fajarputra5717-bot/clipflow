# QA review · e33e0b5 (lane-b) · brief parser: brief text → campaign rules JSON + payout model + unsure fields

Reviewer: Lane C · 2026-10-02 · library only (P3)

Tests: 6 OK. QA ran it on the real IME brief (`docs/campaigns/ime-roleplay.md`): name, category, 6 platforms,
payout `fixed_threshold` Rp 200.000 at 40.000 views (stated CPM kept as informational), max 2 per platform account
per month, budget Rp 20.000.000 in 4 refills, hashtags `required_in_order` (exact list and order), title examples
and language, Discord tag as manual-only: all match the hand-written rules file. 8 `unsure` fields raised, incl.
"uploads after 28 Oct: eligible? (not stated)", "weeks.year read as 2026", watermark asset/preset.

## Findings
1. **Medium (cross-module) · payouts ignores the parser's own doubt.** The parser marks `weeks.outside` as unsure,
   but `shared/payouts.py` (df5445a #1) still advises "not eligible" for uploads after Oct 28. When a rules file
   carries an `unsure` entry for weeks, claim advice should be `unknown`, not `missed`.
2. **Low · weeks are tied to one month.** W1–W4 are emitted as concrete October dates; next month needs a re-parse
   or a manual edit. Fine for a brief-per-month workflow; say so in the Campaign UI.

## Not verified
- Fandra / MotionKlip briefs (their `.md` briefs are still pending verbatim text).
