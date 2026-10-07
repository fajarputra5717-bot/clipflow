# f2b356a (147) P2.5 S3 Schedule view: planned posts by WIB day, overdue on top, week calendar — QA 2026-10-07

GET /api/schedule: WHERE p.user_id = %s AND status planned (owner-scoped). Overdue = scheduled_for < week start, listed
first. UI re-plan / drop / mark use the 146 schedule endpoint and the posts API (schedule-view.spec.js passes).
No bugs found. Not verified: live view vs mock step 6 at 1280/390 (that's for the P2.5 gate).
