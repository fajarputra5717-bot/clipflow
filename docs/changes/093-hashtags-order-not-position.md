# 093 · Campaign hashtags: exact ORDER, at the END (P0, resolves QA 081 #1) · docs/campaigns, shared/campaigns.py

**Decision (2026-10-02).** The briefs require the campaign hashtags in their exact order, not a position.
ClipFlow keeps appending them at the END of the caption (081 behaviour). QA's "must be first" finding came
from rules-file wording ("required_prefix", "first in the caption; nothing before them"), now corrected.

**Now.**
- Rules files: `hashtags.required_prefix` → `hashtags.required_in_order`; `rule` = "exactly these hashtags,
  in exactly this order, together (nothing between them); the brief fixes the ORDER, not the position. ClipFlow
  appends them at the END of the caption."; `position` = "end (ClipFlow convention …)". Lists unchanged.
- `shared/campaigns.hashtags()` reads `required_in_order` (falls back to the old key).
- QA checks: order + contiguity only, not position. v2a "copy caption" keeps them at the end.

**Verified:** backend + worker load the same three lists; `with_campaign_hashtags()` → text, blank line,
hashtags in order at the end.
