# 234f4a0 (144) Publish: one card per clip, per-platform chips + panel — QA 2026-10-07

Playwright (git-served main, mock mode): publish.spec.js 16/16 + QA screenshots, 1280 + 390. No horizontal scroll,
money in IDR (Rp 24.000), panel opens inline on desktop and as a bottom sheet on mobile.
vs mock step 7 (frames: none kept; shots in scratch): the mock lists one row per post with times and a platform filter.
The app has one card per clip with chips plus campaign / left-to-post filters. That's the owner's 144 decision, and
the times belong to P2.5 Schedule. Not a deviation.
Code: telegram_sends.platform NULL = card send. Dedupe uses IS NOT DISTINCT FROM (main.py:2282), so it's OK.
download_name without a platform is campaign_slug.mp4.
Bugs:
1. Low: a card send to Telegram with more than one platform prefixes each caption message with "TikTok:\n" etc.
   (worker telegram send). Copying the whole message on the phone pastes the label into the caption. Send the label
   as its own line/message, or put it in the message entity only.
2. Low, spec seed: the claimed-chip mock row has no views_at / claimed_views / expected_fmt, so the panel reads
   "41.000 not entered yet" and "Claimed at — views · expected Rp ?". The real API sends all three
   (verify live at the gate).
Not verified live: 144 isn't on staging yet (staging = lane-b 649ae25). Requested a restage from Lane B.
