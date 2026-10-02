# QA review · 7d26d57 · 109 campaign rule chips + Approve gate (UI + 409) + content-safety warning (P1)

Reviewer: Lane C · 2026-10-02

Checked: `shared/rule_checks.py` is the single function for UI chips and the approve gate; blocking = length (per-
platform limits from Lane B's research doc), hashtags (exact order at the end, 093), watermark (fails on the
`campaign_watermark` chip); safety = warning only. `POST …/approve` → 409 "Fix N rules to approve: …" (server-side, so a
stale page can't bypass it). `fix-rule` hashtags reuses `with_campaign_hashtags`; dismiss keeps the flags.
`content_safety_check()` runs after a campaign preview, cached by a text+title hash (re-runs only on change; a new
check drops an old dismissal, correct), errors → no chip, `JobCancelled` re-raised; routed via the utility provider
(unknown task → `TEXT_UTILITY_PROVIDER`). Chips aren't progress UI (island rule OK).

## Findings (most severe first)
1. **Medium · Submagic "use as final" bypasses the rule gate.** `submagic_use_as_final()` (`backend/app/main.py`)
   never calls `candidate_rule_failures()`, so a campaign clip with failing hashtags/watermark/length can still become
   a final through the Submagic path. Add the same 409 check there.
2. **Low · one AI call per campaign preview** (cached by text hash). Fine at today's volume; watch cost once
   auto-import (P3) multiplies previews.
3. Info · Lane A's live check flagged IME clip 1a9833d4 (SARA / sensitive issues, the burning + religious
   exclamations): this now covers QA's manual REVIEW item with an in-app warning chip.

## Not verified
- Live UI of chips + "Why?" + Dismiss beyond `rules.spec.js` (mocked); Gemini path of the safety check (Lane A's run
  failed over to Claude Haiku).
