# 415b1ce (148) P2.5 S4 Telegram reminder at the planned time, separate sender — QA 2026-10-07

Deploy: 2026-10-07 03:18Z, riftstorm-sender is new. 6/6 riftstorm-* running, 0 restarts. No errors in sender logs (6 h).
Worker has TELEGRAM_SENDER=separate (skips sends and reminders); sender runs worker.py --telegram-only. No double processing.
queue_due_reminders: FOR UPDATE OF p SKIP LOCKED. Lead is per user and clamped. More than REMINDER_LATE_MAX late → 'missed'
(flagged, not sent). No chat → 'no_chat', retried while still due. Members get no env-chat fallback (admin only), same as 6a.
Bugs:
1. Low: main.py:2332 PATCH /api/posts/{id} changes scheduled_for but doesn't clear reminded_at/reminder_status. The
   schedule endpoint (main.py:2010) does. A post re-timed through the API/token path keeps its old 'sent'/'missed' and
   is never reminded again. The UI re-plans through /schedule, so the UI isn't affected.
Not verified: a real reminder send (owner, production); sender behaviour when the final is still rendering (code path
sends the "⚠ … open ClipFlow → Schedule" note).
