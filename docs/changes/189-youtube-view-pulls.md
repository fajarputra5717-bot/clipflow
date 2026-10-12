# 189 · P5 part 1 — automatic YouTube view pulls (2026-10-12)

- `shared/view_pull.py` (pure, tests/test_view_pull.py): video id from URL/external_id, cadence (every 6 h while a post
  is < 14 days old, daily until 30 days, then stop), batches of 50, parse viewCount, quota day (midnight Pacific),
  error kinds (quota / key / transient).
- Worker `maybe_pull_views()` (idle, every 5 min) → `pull_youtube_views()`: YouTube posts (posted/claimed/paid) that are due,
  `videos.list?part=statistics` with the key in the `X-Goog-Api-Key` header (never in a URL/log), ≤ VIEW_PULL_DAILY_UNITS
  (1000) units per quota day; quotaExceeded stops pulls until the reset; a refused key → alert_admin. Writes like a
  manual entry: clip_posts.views/views_at + clip_post_views row, `source='auto'` (`views_source`, `views_pulled_at`,
  `views_error` for no id / not found). Claim advice + Track read them unchanged. Manual entry stays (views_source manual).
- `view_pull_runs` table (quota accounting); `/api/activity` kind `views` while a run touches the caller's posts →
  island "Updating views…". Settings → YouTube: YOUTUBE_API_KEY (secret, admin-only), VIEW_PULL_DAILY_UNITS.
- Not verified live: no YOUTUBE_API_KEY set yet; Lane B's research marks "API key alone works for public stats" as
  UNCONFIRMED. Check the first run's log line after the key is set.
