# P5 · Automatic view reading + auto-posting (spec, 2026-10-13)

Source: Lane B's `docs/research/publishing-apis.md` (official developer docs, **read 2026-10-02**). Platforms change
these rules often: re-check each platform's pages before building its part. **UNCONFIRMED** = the research could not
confirm it from the official pages.

ClipFlow constraints that decide what works:
- **No public HTTPS URL** for our files → only APIs with a direct/chunked/resumable upload work (all except Threads).
- **No paid services** (roadmap decision) → X (paid per post and per read) is out unless the owner changes that.
- Clips are vertical, H.264 high / yuv420p / AAC 48 kHz / faststart, usually 30–90 s.
- Manual publish (P2, v2a) stays the path for every platform until its auto-post part passes review/audit.

## Status

| Part | What | State |
|---|---|---|
| 1 | YouTube views via Data API v3 `videos.list` (API key) | **Built (189)**: waiting for YOUTUBE_API_KEY |
| 2 | Instagram Reels views (Graph API insights) | Spec below; needs the owner's Meta setup |
| 3 | Facebook Reels views (Page video insights) | Spec below; needs the owner's Meta setup |
| 4 | TikTok views (Display API) | Spec below; needs a TikTok developer app |
| 5 | Auto-post: Instagram Reels (own accounts, Standard Access) | After 2 |
| 6 | Auto-post: Facebook Reels (own Pages) | After 3 |
| 7 | Auto-post: YouTube Shorts (`videos.insert`) | Private-only until Google's compliance audit passes |
| 8 | Auto-post: TikTok (Direct Post) | Private-only until TikTok's app audit passes |
| — | X, Threads | Not planned: X is paid; Threads needs a public video URL |

Every puller writes views the same way as 189 (clip_posts.views + views_at + a clip_post_views row, source `auto`),
so claim advice and Track need no change. Every auto-poster writes `clip_posts` with `source='auto'` through
`shared/posts.py`, runs the same pre-post checks (rule_checks blocking → no post), and shows progress in the island.

## Per platform

### YouTube Shorts — YouTube Data API v3
- **Views:** `videos.list part=statistics` → `viewCount`, 1 quota unit per call (≤ 50 ids). Built in 189 with an API
  key. Whether an API key alone can read public stats is **UNCONFIRMED** in the research: verify on the first run.
  Since 2026-08-24 `viewCount` counts every play start, autoplay included.
- **Auto-post:** `videos.insert` (resumable, scope `youtube.upload`). Own quota bucket: 100 uploads/day; everything else
  shares 10,000 units/day (reset midnight Pacific). No "Short" flag: vertical/square ≤ 3 min is a Short.
- **Gate:** projects created after 2020-07-28 upload as **private** until the project passes Google's API compliance
  audit.

### TikTok — Content Posting API + Display API
- **Views:** Display API `/v2/video/list/` (scope `video.list`, ≤ 20 per page) or `/v2/video/query/`, 600 req/min;
  `view_count` on the Video object. Exact scope needed for the count fields: **UNCONFIRMED**.
- **Auto-post:** Direct Post `POST /v2/post/publish/video/init/` with `FILE_UPLOAD` (chunks 5–64 MB). Must query creator
  info first. 6 requests/min per user token; ~15 posts/day per creator account. Duration via API: 300 s or 10 min
  (**UNCONFIRMED**); our clips are far below either.
- **Gate:** unaudited apps post **private-only**, ≤ 5 users / 24 h. The audit requires this UX: show the creator's
  nickname; privacy chosen by the user from a dropdown with **no default**; comment/duet/stitch off by default;
  commercial-content disclosure; upload only after explicit consent. "API Clients should not add promotional
  watermarks/logos": a campaign's own watermark is the creator's branding, never a ClipFlow mark (how auditors treat it
  is **UNCONFIRMED**).

### Instagram Reels — Instagram Platform (Graph API)
- **Views:** `/{media-id}/insights` → `views` (labelled "in development"), reach, likes, shares…; permission
  `instagram_business_manage_insights` (or `instagram_manage_insights`). Data can lag **up to 48 h**.
- **Auto-post:** container `media_type=REELS` with `upload_type=resumable` (upload to `rupload.facebook.com`) → poll
  status → publish. 100 API posts / 24 h per account. Specs: MOV/MP4, H.264/HEVC, 23–60 fps, 3 s–15 min, ≤ 300 MB.
- **Gate:** Professional (Business/Creator) accounts only. Own/managed accounts = **Standard Access, no App Review**;
  other people's accounts need App Review + Business Verification.

### Facebook Reels — Video API (Pages only)
- **Views:** video insights (lifetime): `fb_reels_total_plays`, `blue_reels_play_count`…; needs `read_insights` +
  `pages_manage_engagement` and a Page token with ANALYZE.
- **Auto-post:** `POST /{page-id}/video_reels` start → binary upload to `rupload.facebook.com` → finish with
  `video_state=PUBLISHED`. 30 API Reels / 24 h per Page. **3–90 s only** (clips over 90 s can't go to FB Reels).
- **Gate:** Facebook **Pages** only (no personal profiles); permissions `pages_show_list`, `pages_read_engagement`,
  `pages_manage_posts`; the user needs CREATE_CONTENT on the Page. App Review tier for own Pages: **UNCONFIRMED**
  (likely the same Standard/Advanced model as Instagram).

### X and Threads (not planned)
- X: pay-per-use ($0.015 per post, $0.005 per read): conflicts with the no-paid-services decision.
- Threads: video must be on a public URL ("We will cURL your video"): blocked for us; reads need
  `threads_manage_insights` + App Review.

## Owner checklist (what only you can set up)

**YouTube (part 1 now, part 7 later)**
- [ ] Google Cloud project → enable **YouTube Data API v3** → create an **API key**, restrict it to that API (and the
      server's IP if you like) → paste into ClipFlow Settings → YouTube → `YOUTUBE_API_KEY`.
- [ ] (Part 7) OAuth client (Desktop/Web) + consent screen; authorise the channel(s) you post to; then apply for the
      **API compliance audit** early, since uploads stay private until it passes.

**Meta: Instagram + Facebook (parts 2, 3, 5, 6)**
- [ ] Each Instagram account you post to is a **Professional** account (Business or Creator).
- [ ] Each Facebook destination is a **Page** you manage (not a profile), linked to the Instagram account if you use
      Facebook Login.
- [ ] Meta developer account → create an app (type Business) → add Instagram (and Facebook Login / Pages) products.
- [ ] Generate a long-lived token for your own accounts with: `instagram_business_basic`,
      `instagram_business_content_publish`, `instagram_business_manage_insights` (Instagram Login), and for Pages:
      `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `read_insights`, `pages_manage_engagement`.
- [ ] Only if you'll ever post for accounts you don't manage: App Review + Business Verification (not needed for your
      own accounts).

**TikTok (parts 4, 8)**
- [ ] TikTok developer account → create an app → add **Content Posting API** (Direct Post) and **Display API**
      (`video.list`) → set redirect URI → authorise your creator account(s).
- [ ] Apply for the **app audit** early (unaudited = private posts only, ≤ 5 users/day). The audit needs the required
      UX above: I'll build it before you submit, and you'll need a short screen recording of it.

**Everyone**
- [ ] Decide per campaign whether auto-posting is allowed at all (some briefs may require posting by hand).
- [ ] Keep `TELEGRAM_*` set: failed auto-posts and refused tokens alert you there.

## Build order + gates
1 (done) → 2 + 3 (one Meta token, views first: low risk) → 5 + 6 (auto-post to own IG/FB, Standard Access) →
4 → 7/8 only as their audits pass. Lane C gate after each part; any open High blocks the next part.
