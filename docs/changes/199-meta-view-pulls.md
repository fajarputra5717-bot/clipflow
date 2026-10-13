# 199 · P5 parts 2+3 — automatic Instagram + Facebook view pulls (2026-10-13)

- One Meta token **per user**: user setting `META_ACCESS_TOKEN` (secret, USER_ONLY: no app_settings/env fallback, so a
  token only ever reads its owner's accounts). A Facebook Login long-lived user token with `pages_show_list`,
  `pages_read_engagement`, `read_insights`, `instagram_basic`, `instagram_manage_insights` covers both platforms
  (Instagram business accounts come through their linked Page). Settings → Instagram & Facebook.
- `shared/view_pull.py`: `instagram_shortcode()`, `facebook_video_id()`, `ig_views()` (insights `views`, `values` or
  `total_value`), `fb_plays()` (`fb_reels_total_plays`, else `blue_reels_play_count`; which one matches the public count
  is UNCONFIRMED: compare on the first run), `meta_error_kind()` (190/102/10/2xx = key; 4/17/32/613/800xx/5xx = transient;
  other 4xx = request = that post only). Same cadence as YouTube (`due()` now covers instagram + facebook).
- Worker `pull_meta_views()` (from `maybe_pull_views()`, separate try so YouTube and Meta never stop each other): per
  user with a token and due posts: `/me/accounts` → each IG account's recent `media` (shortcode → id) and each Page's
  `video_reels` (id → Page token), back to the oldest due post − 2 days, ≤ 10 pages; then `/{media}/insights` and
  `/{video}/video_insights` (Page token). Token always in the Authorization header; paging uses the `after` cursor, never
  `paging.next` (that URL carries the token). ≤ 200 calls per user per run. Writes exactly like YouTube (`views_source`
  auto, `clip_post_views` source auto); not found / no code in URL / no count yet → `views_error`.
- `view_pull_runs`: one row per user, `platform='meta'`, new `token_hash` (sha256 prefix). A refused token (kind key) is
  not retried until the user saves a different token, and the user gets one Telegram note in their OWN chat. YouTube's
  quota sum now counts only `platform='youtube'` runs. Island title "Instagram & Facebook".
- Publish: "· from Instagram / Facebook" (was always "YouTube").
- Verified: throwaway Postgres + worker image, fake Graph API — IG via shortcode + paging stops at the cutoff, FB via the
  Page token, code-100 error only on that post, no-token user + TikTok untouched, the global app_settings value ignored,
  expired token: one failed run, not retried with the same token, retried after a new one, note queued only when the
  member has a chat. Unit 228 OK, UI 225 passed.
- Not verified live: no Meta token yet (owner checklist in docs/tasks/P5-autopost.md).
