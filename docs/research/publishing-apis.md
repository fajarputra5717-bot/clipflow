# Publishing APIs for short video — official requirements

All sources are official developer docs, **read 2026-10-02** (Lane B). Numbers are quoted from
those pages on that day; platforms change them often, so re-check before building. Anything marked
**UNCONFIRMED** was not stated on the pages I read, or the pages contradicted each other.

ClipFlow constraint that matters most: **no public HTTPS URL** for our files (see the Submagic
section in CLAUDE.md). So "public URL required" is a blocker, while "file upload supported" is fine.

## Summary

| Platform | Approval / audit before public posts | Cost | Public URL required? | Video limits (API) | Post rate limit | Read view counts |
|---|---|---|---|---|---|---|
| TikTok | **Yes**: app audit; unaudited = private-only, ≤ 5 users / 24 h | Free (no price on docs) | No: `FILE_UPLOAD` (chunked) or `PULL_FROM_URL` (verified domain) | MP4/WebM/MOV, H.264/H.265/VP8/VP9, 23–60 fps, 360–4096 px, ≤ 4 GB; duration **UNCONFIRMED** (300 s vs 10 min, see notes) | 6 req/min per user token (post init); ~15 posts/day per creator | Yes: `video.list` / `video.query` → `view_count` |
| Instagram Reels | App Review + Business Verification only for accounts you don't own/manage; own accounts = Standard Access | Free (no price on docs) | No: `video_url` **or** resumable upload (`rupload.facebook.com`) | MOV/MP4, H.264/HEVC, 23–60 fps, ≤ 1920 px wide, 3 s–15 min, ≤ 300 MB, 9:16 rec. | 100 API posts / 24 h per account | Yes: media insights `views` (+ reach, likes, shares…) |
| Facebook Reels | App Review for the Page permissions (**UNCONFIRMED** exact path; same Meta model as above) | Free (no price on docs) | No: binary upload or `file_url` header | 9:16, ≥ 540×960 (1080×1920 rec.), **3–90 s**, 24–60 fps, H.264/H.265/VP9/AV1 | 30 API posts / 24 h per Page | Yes: video insights `fb_reels_total_plays`, `blue_reels_play_count`… |
| X | Developer account; no audit stated | **Paid**: pay-per-use, $0.015 per post | No: chunked media upload | Default tier 20 min / 8 GB (docs page; see notes) | 100 posts / 15 min per user; 10,000 / 24 h per app | Yes: `public_metrics.view_count` on media; owned-post extras ≤ 30 days |
| Threads | App Review (`threads_basic`, `threads_content_publish`) | Free (no price on docs) | **Yes**: `video_url` on a public server | MOV/MP4, H.264/HEVC, ≤ 300 s, ≤ 1 GB, ≤ 1920 px wide | 250 posts / 24 h per profile | Yes: media insights `views` ("in development") |
| YouTube Shorts | **Yes**: projects created after 2020-07-28 upload as private until a compliance audit | Free; quota-based | No: resumable upload | ≤ 256 GB, `video/*`; a Short = square/vertical ≤ 3 min | `videos.insert`: own bucket, 100 calls/day by default | Yes: `statistics.viewCount` (`videos.list`, 1 unit) |

## TikTok — Content Posting API

- Scope `video.publish`, approved for the app and authorised by the user; Direct Post endpoint
  `POST /v2/post/publish/video/init/`. Sources: `FILE_UPLOAD` (chunks 5–64 MB, last ≤ 128 MB, 1–1000
  chunks, sequential) or `PULL_FROM_URL` (domain or URL-prefix ownership verified in the dashboard;
  redirects not followed). [Get started], [Direct Post], [Media transfer]
- **Audit:** "All content posted by unaudited clients will be restricted to private viewing mode";
  unaudited = up to 5 users / 24 h. All clients have a 24 h active-creator cap, "typically around 15
  posts per day/creator account". [Guidelines]
- **Required UX** (audit criteria): show the creator's nickname; privacy picked manually from a
  dropdown with **no default**; comment/duet/stitch toggles off by default; commercial-content
  disclosure; upload only after explicit consent; and "API Clients should not add promotional
  watermarks/logos to creators' content". [Guidelines] → A campaign/user watermark is the creator's
  own branding; a ClipFlow-branded mark would break this. **UNCONFIRMED** how auditors treat it.
- Must query creator info before posting (privacy options, limits). Rate limit: "Each user
  access_token is limited to 6 requests per minute" (post init). [Direct Post]
- **Duration conflict:** Get-started says max `300` seconds; the Media Transfer Guide says up to 10
  minutes via API, depending on account. Treat as **UNCONFIRMED**; our clips are < 3 min anyway.
- **Reads:** Display API `/v2/video/list/` (scope `video.list`, ≤ 20 per page) and `/v2/video/query/`,
  600 req/min each; Video Object has `view_count`, `like_count`, `comment_count`, `share_count`.
  [Video list], [Rate limits], [Video object] Scope needed for the count fields: **UNCONFIRMED**.

## Instagram Reels — Instagram Platform (Graph API)

- Professional (Business/Creator) accounts only. Instagram Login: `instagram_business_basic` +
  `instagram_business_content_publish`; Facebook Login: `instagram_basic`, `instagram_content_publish`,
  `pages_read_engagement`. [IG publishing]
- **Access:** "If your app only serves your Instagram professional account or an account you manage,
  Standard Access is all your app needs." Advanced Access (other people's accounts) needs App Review
  and Business Verification. [IG overview] → Fine for our own accounts without review.
- Flow: create container `media_type=REELS` with `video_url` **or** `upload_type=resumable`
  (upload to `rupload.facebook.com`) → poll status (`IN_PROGRESS`/`FINISHED`/`ERROR`/`EXPIRED`
  after 24 h) → publish. "Instagram accounts are limited to 100 API-published posts within a 24-hour
  moving period." [IG publishing], [IG media ref]
- Specs: MOV/MP4, moov atom first, no edit lists; H.264 or HEVC, progressive, closed GOP, 4:2:0;
  AAC ≤ 48 kHz, 1–2 ch, 128 kbps; 23–60 fps; ≤ 1920 px horizontal; 3 s–15 min; ≤ 300 MB;
  video VBR ≤ 25 Mbps. [IG media ref] (Our renders: H.264 high, yuv420p, AAC 48 kHz, faststart: OK.)
- **Reads:** `/{media-id}/insights`: `views`, `reach`, `likes`, `comments`, `shares`, `saved`,
  `ig_reels_avg_watch_time`…; needs `instagram_business_manage_insights` (or
  `instagram_manage_insights`). "Data … can be delayed up to 48 hours", kept 2 years; `views` is
  labelled "in development". [IG insights]

## Facebook Reels — Video API (Pages only)

- "You can only publish Reels to Facebook Pages": **no personal profiles**. Permissions
  `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`; the user needs `CREATE_CONTENT` on
  the Page. [FB Reels]
- Flow: `POST /{page-id}/video_reels` `upload_phase=start` → upload to `rupload.facebook.com/video-upload/{id}`
  as binary **or** with a `file_url` header (rejected if robots.txt blocks it, or for fbcdn URLs) →
  `upload_phase=finish`, `video_state=PUBLISHED`. [FB Reels]
- Specs: 9:16, ≥ 540×960, 1080×1920 recommended, **3 to 90 seconds**, 24–60 fps,
  H.264/H.265/VP9/AV1. **Limit:** 30 API-published Reels / 24 h per Page. [FB Reels]
  → Clips over 90 s cannot go to FB Reels.
- **Reads:** video insights (lifetime only): `fb_reels_total_plays`, `blue_reels_play_count`,
  `fb_reels_replay_count`, `post_impressions_unique`, `post_video_avg_time_watched`…; needs
  `read_insights` + `pages_manage_engagement` and an `ANALYZE` Page token. [FB video insights]
- App Review tier for these Page permissions when used on our own Pages: **UNCONFIRMED** (not on
  the pages read; likely the same Standard/Advanced model as Instagram).

## X — API v2

- **Pricing:** "pay-per-usage pricing. No subscriptions": standard post **$0.015**, post with URL
  $0.200, media metadata $0.005, post reads $0.005 per resource; 3 M post reads / month cap. Price of
  media upload itself: **UNCONFIRMED** (not listed). [X pricing] The only paid platform here, which
  conflicts with the "no paid services" decision.
- Upload: `POST /2/media/upload/initialize` → `/{id}/append` (≤ 5 MB chunks) → `/{id}/finalize` →
  poll `STATUS`; `media_category=tweet_video`; user bearer token. Limits on that page: default
  20 min / 8 GB, Premium 125 min / 16 GB. These are much larger than X's long-standing 140 s /
  512 MB; **UNCONFIRMED** which applies to a non-Premium API account. [X upload]
- Rate limits: `POST /2/tweets` 100 / 15 min per user, 10,000 / 24 h per app; upload initialize/
  append/finalize 1,875 / 15 min per user. [X rate limits]
- **Reads:** `public_metrics.impression_count` (post) and media `public_metrics.view_count` via bearer
  token; non-public/organic metrics (playback quartiles…) need user context, posts ≤ 30 days old.
  [X metrics] Each read is billed.

## Threads — Threads API

- `threads_basic` + `threads_content_publish`, **app review required**. [Threads posts]
- Video: `media_type=VIDEO` + `video_url`. "We will cURL your video using the URL provided so it
  must be on a public server." Create container → wait ~30 s → `threads_publish`. MOV/MP4, H.264/HEVC,
  ≤ 300 s, ≤ 1 GB, ≤ 1920 px wide. [Threads posts] → **Blocked for us** without a public URL
  (would need a short-lived signed URL on a public host). A direct-upload option: **UNCONFIRMED**,
  none found.
- Limit: 250 posts / 24 h per profile (`GET /{id}/threads_publishing_limit`). [Threads limits]
- **Reads:** `/{media-id}/insights`: `views` ("in development"), `likes`, `replies`, `reposts`,
  `quotes`, `shares`; needs `threads_manage_insights`. [Threads insights]

## YouTube Shorts — YouTube Data API v3

- Upload with `videos.insert` (scope `youtube.upload` or broader), resumable, ≤ 256 GB, `video/*`.
  "All videos uploaded via the `videos.insert` endpoint from unverified API projects created after
  28 July 2020 will be restricted to private viewing mode" until the project passes an audit.
  [YT insert]
- **Quota (changed):** `videos.insert` now has its **own bucket: 100 calls/day, 1 unit each**;
  everything else shares 10,000 units/day; resets midnight Pacific. [YT quota] (Older docs had
  1,600 units per upload; this page is current.)
- **Shorts:** no API flag; "square or vertical aspect ratio up to three minutes in length will be
  categorized as Shorts" (uploads from 2024-10-15). [YT Shorts]
- **Reads:** `videos.list` `part=statistics` → `viewCount`, `likeCount`, `commentCount` (1 unit).
  From 2026-08-24 `viewCount` counts "the moment a video begins to play (includes autoplay …)".
  [YT videos] Whether an API key alone is enough for public stats: **UNCONFIRMED** on that page
  (the OAuth token we'd hold for uploads works anyway).

## What this means for ClipFlow (for the roadmap's publishing task)

1. **Works without a public URL:** TikTok (FILE_UPLOAD), Instagram (resumable), Facebook (binary),
   YouTube (resumable), X (chunked). **Threads needs a public URL.**
2. **Audit gates public posting** on TikTok and YouTube. Start both audits early. Until they pass,
   API posts are private-only, so "manual publish" (v2a) remains the path for public posts.
3. **Free:** TikTok, Meta, YouTube. **X is paid per post/read**, against the no-paid-services decision.
4. **Caps that shape scheduling:** TikTok ~15 posts/day per creator, FB 30 Reels/day per Page,
   IG 100/day, YouTube 100 uploads/day per project. All are above our planned 2–6 posts/day per account.
5. **Clip length:** FB Reels ≤ 90 s is the tightest limit. Shorts ≤ 3 min; TikTok API up to 300 s or
   10 min (UNCONFIRMED); IG ≤ 15 min.
6. **View counts are readable on all six;** IG data can lag up to 48 h, and X charges per read.

## Sources (all read 2026-10-02)

- [Get started]: https://developers.tiktok.com/doc/content-posting-api-get-started
- [Direct Post]: https://developers.tiktok.com/doc/content-posting-api-reference-direct-post
- [Media transfer]: https://developers.tiktok.com/doc/content-posting-api-media-transfer-guide
- [Guidelines]: https://developers.tiktok.com/doc/content-sharing-guidelines
- [Video list]: https://developers.tiktok.com/doc/tiktok-api-v2-video-list
- [Video object]: https://developers.tiktok.com/doc/tiktok-api-v2-video-object
- [Rate limits]: https://developers.tiktok.com/doc/tiktok-api-v2-rate-limit
- [IG publishing]: https://developers.facebook.com/docs/instagram-platform/content-publishing
- [IG media ref]: https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media
- [IG insights]: https://developers.facebook.com/docs/instagram-platform/reference/instagram-media/insights
- [IG overview]: https://developers.facebook.com/docs/instagram-platform/overview
- [FB Reels]: https://developers.facebook.com/docs/video-api/guides/reels-publishing
- [FB video insights]: https://developers.facebook.com/docs/graph-api/reference/video/video_insights
- [X pricing]: https://docs.x.com/x-api/getting-started/pricing
- [X upload]: https://docs.x.com/x-api/media/quickstart/media-upload-chunked
- [X rate limits]: https://docs.x.com/x-api/fundamentals/rate-limits
- [X metrics]: https://docs.x.com/x-api/fundamentals/metrics
- [Threads posts]: https://developers.facebook.com/docs/threads/posts
- [Threads limits]: https://developers.facebook.com/docs/threads/troubleshooting
- [Threads insights]: https://developers.facebook.com/docs/threads/insights
- [YT insert]: https://developers.google.com/youtube/v3/docs/videos/insert
- [YT quota]: https://developers.google.com/youtube/v3/determine_quota_cost
- [YT videos]: https://developers.google.com/youtube/v3/docs/videos
- [YT Shorts]: https://support.google.com/youtube/answer/15424877
