# 7c2b549 (159) P3 part 3: Campaign step cards (status, payout sentence, my totals, budget, cap) — QA 2026-10-07
Cross-user: _campaign_stats queries clip_posts WHERE user_id = %s. Live: lane-c-a IME mine = posted 6 / claimed 2 / paid 1 /
planned 1, Rp 200.000 paid; lane-c-b Fandra mine = 1/1/1, Rp 156.000. Each matches only that user's own posts.
No bugs found. Not verified: UI vs mock step 1 at 1280/390 (the P3 gate).
