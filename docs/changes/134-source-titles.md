# 134 · Bug: every job titled "AI-Generated Highlight" → YouTube title from yt-dlp; short job id · worker.py, index.html

- `source_videos.title` was never written, so `jobDisplayTitle()` (job name → source title → …) fell through to
  "AI-Generated Highlight". The worker's download pre-flight already ran `yt-dlp -j`; it is now `youtube_info()`,
  and `store_source_title()` saves the title (only when empty) before the size estimate. A job name you set still wins.
- Backfill for older sources: `backfill_source_titles()` (metadata only, `with_format=False`) runs at worker start
  (up to 20) and in the idle sweep (3 per sweep); a video yt-dlp can't read is tried once per process.
- Review cards and the job header show the id short and small ("#5a188a88"); the full id is in the tooltip.
- Deploy incident: the first build referenced `YTDLP_FORMAT` in a default argument before its definition →
  the worker crash-looped ~3 min on prod (idle, no job affected) until the fix (`with_format` flag) was deployed.

**Verified (prod):** worker up, 9/10 source titles backfilled from YouTube (1 needs cookies: bot check), harness passed.
