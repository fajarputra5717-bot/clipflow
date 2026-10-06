# QA review · d19b286 (lane-b) · editor: real P1.5 user + owner scoping, routes under /api/jobs/{jid}/candidates/{cid}/editor
Reviewer: Lane C · 2026-10-06 · Fixes a67d58c #1 (HIGH). Live on staging: qa_a GET/PUT own clip editor 200/200; **qa_b on A's clip 404/404** ✓; routes now also under main's middleware guard. Note (Low): staging restores production users + sessions; cookies are host-scoped, so a production login cookie also works on :8080.
**Merge: OK.**
