# 133 · P2 part 5: claim advice per post, time-stamped views, Mark claimed (views + expected payout), Mark paid (actual + difference) · main.py, index.html

- **Advice** on each posted row = `payouts.claim_advice()` (Lane B, 131) fed by: views, posted_at, the campaign's
  `period` end, `account_claims_this_month` (eligible claimed/paid posts on that account + campaign in the upload's
  WIB month) and `views_24h_ago` (newest views entry 18–48 h old, else None). Shown as Claim now / Wait / Missed /
  Check brief + the message (payout if claimed now, views still needed, deadline "claim by …"). A post stored as
  not eligible (132) shows Missed + its reason. Money strings come formatted from the API (`format_idr` /
  `format_with_idr`); index.html never formats or computes payouts.
- **Views:** `PATCH /api/posts/{id} {views}` stamps `views_at` and appends to new owned table `clip_post_views`
  (post_id, user_id, views, at). Row: "Views 45.500 as of 6 Oct · 14:20" + input.
- **Mark claimed** (posted → claimed) submits the views at claim time (400 without views): stores `claimed_views`
  and `expected_rp = payouts.payout_for(model, claimed_views)` in IDR (Fandra pays on submitted views).
- **Mark paid** (claimed → paid) asks for the amount actually received (prefilled with expected); the row shows
  "Paid Rp 168.000 · expected Rp 180.000 · −Rp 12.000".
- **fandra-octo.rules.json:** `max_payout_per_video` was already 1992000 on main (corrected 2026-10-02 with the
  block-math note); Lane B's note in 131 referred to an older copy. No change needed.

**Verified:** harness 81 passed (+ advice, views as of, claim with views → expected, paid → difference); prod
read-only: new columns + clip_post_views present, queue 200, unknown post 404; prod code without DB: Fandra 45.500
views → Rp 180.000 (cap Rp 1.992.000), paid 168.000 vs expected 180.000 → "−Rp 12.000", IME 41k views 1 day after a
W1 upload → claim_now with deadline 8 Oct 00:00 WIB, Fandra +9.000/24 h → wait ("about Rp 216.000 tomorrow").
Real claim/paid writes → staging.

**Staging write checks (2026-10-06, 24ce3eb, members qa-tmp-a/qa-tmp-b; covers 128–133): 35/35 pass.** Accounts
(create, @ stripped, duplicate 409, bad platform 400, B's PATCH 404, lists scoped); a clip failing an Approve rule
(IME hashtags) → posting 409 "Fix before posting"; with hashtags fixed: posts 1–2 eligible, post 3 on the same
account → `eligible=false`, "Cap reached for @qa_a_tt on TikTok this month (2 of 2)"; duplicate link 409, http/
wrong host 400; B can't read/patch/delete A's post or post A's clip (404); lifecycle (posted→paid 409, claim without
views 400, paid needs amount, paid is final, posted can't be deleted, drop then delete ok); views stamped + history
row; IME 41k inside W1 → claim_now; claimed at 42k → expected Rp 200.000; paid 190.000 → "−Rp 10.000"; account with
posts → paused. Staging data changed for this: qa-tmp-a's job 0957133b tagged ime-roleplay, a paused account, 3 posts —
and, wrongly, Lane C's job 2ee13f97 (qa_a's IME import): reassigned, tagged, 2 clip descriptions overwritten, 1 post
(dropped + deleted). Reported to Lane C; staging test data is now per lane (lane-a-* only).
