# P2 write checks on staging (b0d73b9 = main 24ce3eb) · QA members qa_a / qa_b · 2026-10-06 · **22/22 PASS**
Posting accounts: A add 200 · duplicate 409 · B's list excludes A's account · B GET/PATCH/DELETE A's account **404** ·
A pause 200 / resume 200 · A remove an account that has posts → 200, account kept paused (`active=false`), not deleted.
clip_posts: A create planned 200 · B create on A's clip **404** · B GET/PATCH/DELETE A's post **404** · B's list
excludes A's post · flow planned→posted (url + posted_at) → views 45 000 → claimed (expected Rp 200.000, advice
"Already claimed.") → paid (paid_rp 200 000) all 200 · paid→planned refused 409 · duplicate link 409.
Cap (IME 2 per account per month): posts 1–2 eligible=true; post 3 stored **eligible=false**, `ineligible_reason`
"Cap reached for @qa_lanec_tt on TikTok this month (2 of 2)".
Setup (staging only): reassigned staging job 1522410e to qa_a (campaign ime-roleplay) and added hashtags via
fix-rule; returned qa_a's own job 2ee13f97, which Lane A had reassigned to qa-tmp-a. Account @qa_lanec_tt (paused),
3 posts. (Two FAILs in the raw run were QA script bugs, re-verified via the API.)
