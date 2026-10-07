# Gate P2.5 (Schedule): PASS, 2026-10-07

Staging = main 0a81ae5 (145–148 + lane-b merge), rebuilt by Lane B. Members lane-c-a / lane-c-b. Open Highs: none.

| Area | Result | Evidence |
|---|---|---|
| S1 posting times per user, WIB (145) | PASS | gate-P2 addendum: lane-c-b edit saved (source=user), lane-c-a keeps the defaults |
| S2 schedule-plan: future WIB suggestions per account | PASS | Facebook 12:00/19:00 → next 3 slots, all future |
| S2 Approve & schedule: approve queues final + version, planned post at slot | PASS | approved=true, render_queued → completed |
| S2 guards: past 400, dup platform 400, account/platform mismatch 400, window (30 Oct ineligible "W1–W4") | PASS | tests/qa-p25-writechecks.py 19/19 |
| S2 re-plan keeps post id; posted platforms + no-account platforms disabled in sheet | PASS | live sheet 1280/390 |
| S3 Schedule view: rows by WIB day, Telegram-not-set banner, free slots, re-plan sheet, drop, mark posted | PASS | live staging 1280/390, 0 JS errors, no h-scroll |
| S3 vs mock step 6 | PASS (expected deviation) | mock = US prime time ET; app = owner-approved WIB slots |
| S4 reminders: due post reached by reminder pass; no bot → no_chat; staging has no separate sender (worker runs it) | PASS | reminder_status no_chat; real send: owner on prod |
| Cross-user: B on A's schedule-plan/schedule/drop → 404; B's /api/schedule excludes A | PASS | 19/19 |
| Render after schedule (IME, 23855acf) | PASS | 1080x1920, 36.0 s, -14.5 LUFS / -1.1 dBTP, full-frame, karaoke, watermark ≈27 %; frames/p25-ime-schedule-final.jpg |
| Fandra e2e | PASS (cited) | fresh import f8db9018 today (gate-P2), same render path |
| Production after 146–148 deploy | PASS | 6/6 riftstorm-* running, 0 restarts (incl. sender) |

Corrections: 148 Low withdrawn (QA error). Open Lows: P2 list only. Not covered here: production post-merge check (0a81ae5),
see the post-merge note once Lane A deploys.
