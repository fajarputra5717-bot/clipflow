# P1.5 live test on staging · BLOCKED (2026-10-06)
Requested: run qa-multiuser.spec.js + member global-settings 403 on staging (main P1.5 parts 1–3 + lane-b).
Found: staging does NOT run P1.5.
- Staging backend (built 2026-10-05 22:24 from /opt/clipflow-lane-b) has no `_path_owned` / `USER_SETTING_KEYS`;
  staging DB has no `users` table; `/api/auth/me` → 401 from the old key middleware.
- lane-b's last main merge (1e10162) stops at 54f04e9 (P1.5 spec doc): 120 (da2e287), 122 (0cea7b2), 123 (40b31a7)
  are NOT in lane-b. The lane-b worktree is also "ahead 4" of origin/lane-b (unpushed).
- No way to create member users on main: the only `INSERT INTO users` is the env bootstrap admin
  (`auth.py:160`); the spec's admin page (create/disable users, reset passwords) isn't built yet.
Needed: (1) Lane B merges main ≥ 40b31a7 into lane-b and runs `scripts/staging.sh up` (or reset); (2) Lane A ships
the admin user-management part (or a CLI) so QA can create members A and B on staging. Then QA runs the spec
(guarded to :8001/:8080) and the 403 check.
Code reviews of 120–123 are done (da2e287/0cea7b2/40b31a7/f380dd5-review.md); live verification pending.
