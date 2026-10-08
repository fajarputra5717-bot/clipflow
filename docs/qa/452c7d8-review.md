# 452c7d8 (167) yt-dlp bot-check hardening · Lane C static review · 2026-10-09
Prod after deploy: riftstorm-{backend,worker,sender,pot,notifier,frontend,postgres} running, restarts=0 (worker/pot/sender started 2026-10-08T18:49Z).
No High found. Invariants: new yt-dlp calls go through shared/ytdlp.py, cancel check inside wait_turn, failure is permanent + admin Telegram alert once/h: matches CLAUDE.md (R-08/R-15).
1. Medium · lane-b's shared/source_watch.py (3d12912) runs yt-dlp itself, without ytdlp.base_args / wait_turn / bot-check handling; after merge its listings hit the bot check and bypass the 20 s spacing (167's own docstring says it should use them).
2. Low · wait_turn holds the flock while sleeping: every yt-dlp call queues behind it, so N jobs add ~20-26 s each to start; intended, but a stuck sleeper blocks the metadata step of other users.
3. Low · YTDLP_COOKIES_FILE is a DB-editable setting (admin only): any readable path is copied to a temp file and handed to yt-dlp.
Not verified: a FRESH import end to end (needs a per-user admin cf_ token on prod; none available to QA), PO-token provider working under load.
