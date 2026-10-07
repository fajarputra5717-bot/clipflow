# 148 · P2.5 S4: Telegram reminder at the planned time (+ send-to-phone package), separate `sender` service · worker.py, main.py, compose, digest, index.html

- **Why:** P2.5 spec S4. No auto-posting: ClipFlow reminds, the user posts.
- **Deviation from the spec (notifier → sender):** the notifier is read-only by design (142: read-only DB session,
  text only) and the main worker can be busy 10+ min with one analysis, which would make a 15-min-lead reminder
  late. So reminders + the Telegram queue run in a new compose service **`sender`** (`riftstorm-sender`: the worker
  image, `worker.py --telegram-only`, /data mounted for finals). The worker gets `TELEGRAM_SENDER=separate` and
  then skips Telegram; without it (lane-b staging) the worker does both while idle, as before.
- **Queueing (`queue_due_reminders()`, every 30 s):** `clip_posts` planned, `scheduled_for` set, `reminded_at` NULL,
  due within the owner's `REMINDER_LEAD_MIN` (user setting, default 15, 0–120; PUT validates) → one
  `telegram_sends` row `kind='reminder'` (+ new `post_id`) to the owner's OWN chat (user_settings TELEGRAM_CHAT_ID;
  admin → env TELEGRAM_CHAT_ID; members never) and `reminded_at` + `reminder_status='queued'` in the SAME
  transaction (`FOR UPDATE SKIP LOCKED`). > 1 h late (downtime) → `missed`, not sent. No bot/chat → `no_chat`,
  retried each pass while still due. Re-plan (PATCH `scheduled_for` / schedule POST with a new time) clears both.
- **Send:** "⏰ Post now: TikTok @imeclips · 19:00 WIB · IME Roleplay", then the 141 package for that platform
  (video ≤ 50 MB or shrunk, caption as its own message); no final yet → a "⚠ … open ClipFlow → Schedule" line
  instead; post no longer planned → closed without sending. `reminder_status` → sent / failed. Island progress via
  the existing activity kind `telegram`.
- **Lane C Low (144):** a multi-platform card send puts "⬇ TikTok caption" in its own message before each caption,
  so a long-press copies the caption alone.
- **Schedule view:** reminder chip per row (on its way / sent / failed / missed / no chat), a banner when the
  Telegram chat isn't set up (`telegram_ready`), else "Telegram reminder N min before each post".
  Settings → Posting times: "Telegram reminder [15] min before". **Digest (142):** "🕒 Scheduled today" section.
- Schema readiness now checks the newest column (`telegram_sends.post_id`, last statement).

- **Fix (Lane C Low, qa d8517f5):** `PATCH /api/posts/{id}` clears `reminded_at`/`reminder_status` whenever `scheduled_for`
  actually changes (was only inside the re-check, skipped e.g. for a post whose clip is gone).
**Verified:** UI 109 passed (reminder chips/banner, lead save); unit tests OK; prod deploy: backend healthy
(schema ready), worker `TELEGRAM_SENDER=separate`, sender "Telegram sender started", 0 restarts; columns present;
`--preview-digest` OK. Real reminder delivery = owner (prod Telegram); staging write checks after lane-b merges
main (lane-b's staging compose has no `sender`; its worker handles reminders).
