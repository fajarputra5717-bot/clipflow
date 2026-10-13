# 200 · Meta view pulls: Lane C's 3 Lows on 199 (2026-10-13)

Lane C review of 4a20c78 (qa 2ea735f): PASS (conditional, no live Meta token), 3 Lows, all fixed:
1. Facebook insights: a code-100 reply to the combined `fb_reels_total_plays,blue_reels_play_count` request is retried
   one metric at a time, so one name Graph rejects no longer blanks every Facebook post.
2. `meta_error_kind(..., per_object=)`: permission errors (10, 2xx) on a call about one media/Page/video are that
   post's problem (`request` → views_error on it); only on `/me/accounts` do they mean the token lacks a permission
   (`key`). 190/102 stay `key` everywhere.
3. An unexpected exception in one user's run is logged, stored on that run row (failed, transient) and the next user
   still runs.
Verified: throwaway Postgres + fake Graph (code-10 media → error on that post only, the other IG post and the FB post
via the single-metric retry counted, a crashing user didn't stop the other); unit tests OK.
