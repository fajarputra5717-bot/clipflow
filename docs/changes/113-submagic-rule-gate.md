# 113 · Submagic "use as final" goes through the campaign rule gate (QA Medium on 109) · main.py, index.html

`POST …/submagic/use-as-final` adopts a Submagic render as the clip's final, but skipped 109's gate. It now runs
the same `candidate_rule_failures()` check as Approve and answers 409 "Fix N rules to approve: …" before
queueing the apply. UI: the "Use as final render" button is disabled with "Fix N rules to use as final" while a
blocking chip fails (same `ruleFailures(c)` as Approve).

**Verified:** IME clip 1a9833d4 with `submagic_status='completed'` and no hashtags → 409 "Fix 1 rule to approve:
Hashtags missing or out of order", status stayed `completed` (nothing queued); state restored; harness green.
