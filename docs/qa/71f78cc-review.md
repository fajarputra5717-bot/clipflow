# 71f78cc (166) New campaign from a pasted brief · Lane C static review · 2026-10-09
Admin-only on all three routes (403 for members): OK. Parse metadata is stripped before saving; 409 gate for unconfirmed unsure fields; slug unique (ON CONFLICT) : OK. Playwright campaign-new spec passed in the full run.
1. Low · the 409 gate trusts the client's `unsure` list: POST with unsure=[] saves unconfirmed AI fields (admin-only, so a UI-bypass, not a privilege issue). Re-derive from the stored parse or drop it.
2. Low · create does not run _rules_preview/validate payout shape; only platforms are checked. A malformed payout saves, then get_campaign (the 201 body) may raise 500 with the row already stored. Not verified.
Not verified: AI-filled fields on a real brief (Gemini/Claude call), prod create flow.
