# 141 · P2 part 6a: "Send to phone" via Telegram — per-user chat, worker queue, ≤ 50 MB or re-encoded · main.py, worker.py, index.html

Owner decisions (2026-10-07): one bot (env TELEGRAM_BOT_TOKEN), each user's OWN chat; files sent by a worker queue.
- **Chat:** Account sheet → Telegram: your chat id (`user_settings` key TELEGRAM_CHAT_ID; number from @userinfobot or a
  @channel), Save, Send test. `GET/PUT /api/telegram` (shows the bot's @name via getMe, cached 1 h). An admin without
  one falls back to env TELEGRAM_CHAT_ID; a member never does (no clip of theirs reaches the admin's chat).
- **Queue `telegram_sends`** (owned, kind clip|test, chat_id snapshotted, queued→sending→sent|failed, progress,
  attempts, retry_after, mode video|reencoded|too_big). `POST /api/publish/send-to-phone {candidate_id, platform}`
  (own clip with a final, else 404/409; one in flight per clip+platform), `POST /api/telegram/test`.
- **Worker** `claim_telegram_send()` (FOR UPDATE SKIP LOCKED, after renders/Submagic in `main()`, run as the job owner):
  message 1 = the final mp4 (sendVideo, short caption "title / platform · campaign_platform_slug.mp4"); over 50 MB →
  `shrink_for_telegram()` re-encodes to ~45 MB (H.264, AAC 96k, watchdog timeout, disk reserve, temp file named by the
  send id and deleted) and says so; if it can't fit sensibly → a text saying to download it from Publish. Message 2 =
  the post caption alone (same rules as the Publish row: hashtags in order, platform limit) for one long-press copy.
  429/5xx/network → retry (2, 4 min; max 3 attempts); "chat not found"/403 → failed with "press Start in your bot".
  Startup requeues an interrupted send; a missing table (fresh deploy, backend not migrated yet) is tolerated.
- **Progress:** `GET /api/activity` kind "telegram" → the island capsule; the Publish row shows "Sending to your
  phone…" / "Sent to phone <time>" / "Send to phone failed: …" and refreshes when the send ends.

**Verified:** harness 87 passed (+ Account chat id validation/save/test, Send to phone payload + row status);
re-encode in a throwaway container on a real 19.2 MB final with a 5 MB target → 5.0 MB, too-long clip → None; both
images import ok; prod read-only: `/api/telegram` (bot @aiclipmonitorbot, source env, ready), send-to-phone unknown
clip 404 / bad platform 400, no rows created. Deploy note: the first worker start raced the backend's migration
(UndefinedTable, one restart) → guarded. Real sends are for the owner to try (they go to his phone).

**Staging (lane-b f442569 = main eb28421, no TELEGRAM_*), lane-a-tg1/tg2:** 9/9: bot_configured false; invalid chat id
400; own chat id saved (source user); another member sees none and has no fallback; test send → 409 "isn't set up" (no
row queued); send-to-phone unknown/other's clip 404, bad platform 400; clearing works; activity 200.
