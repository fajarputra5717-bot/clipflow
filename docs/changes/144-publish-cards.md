# 144 · P2 fix: Publish = one card per clip with per-platform status chips (UI; same clip_posts model) · index.html, main.py, worker.py, shared

- **Why (owner 2026-10-07, before the P2 gate closes):** one row per clip × platform repeated the same clip 3–4
  times; the owner wants one card per clip with each platform's state visible at a glance.
- **Card:** thumbnail, title, caption preview, source (job title, small), summary "Posted on N of M · Rp X
  expected", shared actions Download (`?download=clip` → `campaign_slug.mp4`), Copy title, Send to phone.
- **Platform strip:** one chip per allowed platform: Ready / Planned / Posted @account / Claimed / Paid, amber
  "Not eligible" (pre-post warnings on a ready row, or a post stored `eligible=false`), red "Blocked" (Approve-
  blocking rule failures), plus "N views". Tap → that platform's panel: Copy caption (platform-trimmed), Mark
  posted (account + link), Open post, views, claim advice, Mark claimed / paid, checks. One panel per card; Escape /
  ✕ closes and returns focus to the chip. ≤ 600 px it is a bottom sheet rendered into `#publishSheetHost`
  (body level: every `.view-section` carries a transform, which traps `position:fixed`); only in the DOM while open.
- **Filters:** campaign (segmented) + "Left to post" (default: a card with any Ready chip; an open card stays until
  closed) / All. The platform filter is gone.
- **API (additive):** `GET /api/publish-queue` groups gain `cards[]` (`candidate_id, job_id, job_title, title,
  caption, has_thumbnail, filename, platforms, summary{posted,total,expected_fmt}, last_send`); `rows` unchanged.
  Expected = claimed/paid `expected_rp` + posted posts' claim-advice amount now (`advice.payout_now_rp`, new,
  `payouts.to_idr`), formatted by `payouts.format_idr`. `POST /api/publish/send-to-phone` `platform` optional:
  omitted = the video once + one caption message per platform ("TikTok:\n…"); duplicate guard per
  (clip, platform-or-NULL). `posts.clip_platforms(rules, job_platform)` = the one platform-list rule (queue,
  digest, worker); `posts.download_name(campaign, None, title)` = no platform segment.
- **Also fixed:** switching to Publish never removed `.switching-in` (early return), leaving its animation class on.

**Verified:** UI suite 89 passed / 5 skipped (desktop 1280 + mobile 390; publish.spec rewritten for cards, chips,
panel, sheet, filters, send body); screenshots `tests/ui/test-results/publish-{cards,panel}-{1280,390}.png`.
