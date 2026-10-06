# 130 · P2 part 3: Publish step (flow-preview step 7 "Publish queue"): download, copy title/caption, Mark posted, post status · main.py, shared/posts.py, shared/campaigns.py, index.html

- **Stepper:** Publish is live (`data-nav="publish"`, `#publishSection`, page title "Publish"); mobile tab bar gains
  Publish (grid now auto-columns: one row for any item count). `showTab()` handles 3 views (`TAB_SECTIONS`, slide
  direction follows stepper order).
- **`GET /api/publish-queue`** (own jobs): one row per finished clip (status completed + final_path) × allowed
  platform (campaign `platforms`, else the job's Analyze platform via `posts.JOB_PLATFORM`), grouped by campaign.
  Caption = `campaigns.caption_body(description)` (new, shared with `with_campaign_hashtags`, output unchanged) +
  campaign hashtags in exact order; `posts.trim_caption()` shortens only the body to the platform limit
  (`CAPTION_LIMITS`: TikTok/IG/FB 2200, YouTube 5000, Threads 500, X 280; "Caption shortened" note), titles to
  YouTube's 100. Each row carries its latest post (a live one wins over a dropped one).
- **Download:** `…/render?download=<platform>` → `Content-Disposition: attachment; filename=campaign_platform_slug.mp4`
  (`posts.download_name`, ASCII slug; no campaign → `clip_`). Unknown platform 400. Same route, same ownership guard.
- **Copy:** `copyText()` calls the Clipboard API synchronously inside the tap (iOS Safari requirement) and falls back
  to a selected off-screen textarea + `execCommand("copy")` for older WebKit/insecure origins; "Copied" feedback.
- **Mark posted:** inline form (active accounts of that platform + https link) → `POST /api/posts` (status posted);
  no account → "Add one in Settings → Posting accounts". Status badges Ready / Planned / Posted / Claimed / Paid
  with posted time, @account and "open post". Platform filter (All + platforms present), short names like the mock.

**Verified:** unit tests 13 OK; harness 77 passed (+ publish.spec: grouping/filter/statuses/download name, copy via
Clipboard API and via the execCommand fallback, Mark posted no-account hint + payload + Posted badge, tab bar one
row); screenshots vs mock step 7 at 1280 and 390; prod read-only: queue = 61 rows (Fandra 12, IME 36, Windah 6, no
campaign 7), caption ends with the campaign hashtags in order, download → 206 + `attachment;
filename="fandra-octo_tiktok_….mp4"`, unknown platform 400. Mark posted on real data = a write → staging.
