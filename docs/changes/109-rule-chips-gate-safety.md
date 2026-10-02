# 109 · Campaign rule chips + "Fix N rules to approve" gate + content-safety warning (P1 editor commit 3) · shared/rule_checks.py, main.py, worker.py, index.html, tests/ui

**Now.**
- `shared/rule_checks.py` (pure; one function for UI and API): campaign clips only.
  - **length** (blocking): clip duration within every campaign platform's limit, from Lane B's
    `docs/research/publishing-apis.md`: Facebook Reels 3–90 s, Instagram Reels 3–900, YouTube Shorts ≤ 180,
    TikTok ≤ 300 (API limit unconfirmed: the conservative value), Threads ≤ 300, X ≤ 140. No fix until the
    P4 trim timeline.
  - **hashtags** (blocking): description ENDS with the campaign hashtags in order, together (093). Fix: "Add
    hashtags" → `POST …/fix-rule {rule: "hashtags"}` (reuses 081's `with_campaign_hashtags`).
  - **watermark** (blocking, when the campaign requires one): fails on a `campaign_watermark` render warning
    (092/099).
  - **safety** (warning only, never gates): from `clip_candidates.safety_check`; "Why?" lists rule, quote,
    reason; "Dismiss" (`fix-rule {rule: "dismiss"}`) records `dismissed: true`, flags kept.
- `GET /api/jobs/{id}` adds `rule_checks` per candidate; `POST …/approve` answers 409 "Fix N rules to approve:
  …" while a blocking chip fails (so a stale page can't bypass the UI gate).
- Worker `content_safety_check()`: after a campaign clip's preview, one utility-model pass (`task=
  "content_safety"` → TEXT_UTILITY_PROVIDER) over the clip words + title against the campaign's clip-checkable
  content rules; stores `{flags, checked_at, provider, model, text_hash}`; re-runs only when text/title change;
  errors log and leave no chip.
- UI: chips under the clip title (mockup `.checks`, badge tokens), the action button is now **Approve**
  (renders the final), disabled with "Fix N rules to approve" while a blocking chip fails, plus the hint line.

**Verified** on the stack: IME job → chips for both clips; clip 1a9833d4 really had no hashtags (its
description had never been generated) → 409 on approve → "Add hashtags" fixed it (original empty text + tags);
content check on 1a9833d4 → 2 flags (no_sensitive_issues: "Kebakar Lagi…" title; no_sara_or_insults:
"Astaghfirullahaladzim… sihir" + burning; the same item Lane C raised for manual review), served by Claude
Haiku after a Gemini 503 failover; chips + "Why?" in the UI, Approve enabled (warning only); harness 28/28
with the new `rules.spec.js`.
