# P4 task 6 — shared/source_watch.py (lane-b)

`check_channel(channel, backfill=0)` → new uploads + finished livestreams `{video_id, url, title, duration,
published_at, is_live_done}`. Listing = `yt-dlp --flat-playlist -J` on /videos + /streams; times = channel RSS
feed (per-video yt-dlp metadata is bot-blocked on this server, so no per-video calls). Dedup state in
`/data/source_watch/<channel_id>.json`; first check baselines (returns []); live/upcoming waits until finished.
Checked live on @FandraOcto (listing, live stream skipped, dedupe, RSS dates). Tests: `tests/test_source_watch.py`.
Lane A wires it into P3 part 7.
