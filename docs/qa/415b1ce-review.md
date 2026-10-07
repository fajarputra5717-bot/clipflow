# 415b1ce (148) P2.5 S4 Telegram reminder at the planned time, separate sender — QA 2026-10-07

Deploy: 2026-10-07 03:18Z, riftstorm-sender is new. 6/6 riftstorm-* running, 0 restarts. No errors in sender logs (6 h).
Worker has TELEGRAM_SENDER=separate (skips sends and reminders); sender runs worker.py --telegram-only. No double processing.
queue_due_reminders: FOR UPDATE OF p SKIP LOCKED. Lead is per user and clamped. More than REMINDER_LATE_MAX late → 'missed'
(flagged, not sent). No chat → 'no_chat', retried while still due. Members get no env-chat fallback (admin only), same as 6a.
Bugs: none.
CORRECTION 2026-10-07: the earlier Low #1 ("PATCH /api/posts doesn't reset the reminder") was WRONG. 415b1ce
main.py:2358 already cleared reminded_at/reminder_status whenever scheduled_for was sent. My grep output was truncated
before that line. Lane A's a3c3dbb narrows it to "only when the time actually changes" (reviewed: OK, _parse_ts accepts the
stored value). Withdrawn.
Not verified: a real reminder send (owner, production); sender behaviour when the final is still rendering (code path
sends the "⚠ … open ClipFlow → Schedule" note).
