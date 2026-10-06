# 142 · P2 part 6b: personal daily digest at 09:00 WIB in each user's own Telegram chat · shared/digest.py, shared/post_advice.py, notifier, main.py

- **Who/where:** the notifier sends one digest per active user per day at/after `DIGEST_HOUR` (env, default 9, WIB) to
  that user's own chat (user_settings TELEGRAM_CHAT_ID from 141; admin without one → env TELEGRAM_CHAT_ID; a member
  never gets the admin's chat). Dedupe per user per day in state.json (`digest_dates`); catches up after a restart;
  a day with nothing to say sends nothing. The 08:00 ops summary and the ops alerts are unchanged.
- **What (`shared/digest.py`, read-only, every query scoped by user_id):** Ready to post (finished clips × allowed
  platform without a live post, same rows as Publish; top 5 + "+N more"); Claim now (posts whose advice is
  claim_now, payout + deadline); Closing within 48 h (waiting posts, views still needed); Update views (posted posts
  whose views are > 24 h old); week-window campaigns (IME): the open week and when it closes.
- **One source:** the claim-advice glue moved from main.py to `shared/post_advice.py` (`advice_for`,
  `views_day_ago`, `claims_this_month`, `wib_month_bounds`); main.py's Publish rows and the digest both call it.
- **Notifier image:** now gets `shared/` (compose additional_contexts) + `docs/campaigns` mounted read-only at
  /app/campaigns; still read-only DB, no inbound surface. `python notifier.py --preview-digest` prints every user's
  digest and sends nothing.

**Verified:** notifier + backend images import ok; `--preview-digest` on prod data (read-only): admin → "Ready to
post: 61 (18 clips)" with 5 titles + platforms, "IME …: week W1 open, closes Wed 07 Oct 23:59 WIB"; notifier
restarted 00:13 WIB (before 09:00, nothing sent), log shows "digests 09:00 WIB"; harness and unit tests passed.
First real digest: 09:00 WIB 2026-10-07 to the admin chat.
