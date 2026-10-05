# P1.5 gate checklist (draft) · multi-user accounts

Source: owner messages 2026-10-05 (spec partly truncated; see memory p15-multi-user). Any open High = BLOCKED.

## Cross-user isolation: every failure is HIGH (owner 2026-10-05)
Automated: `tests/ui/specs/qa-multiuser.spec.js` (Playwright request API, two members A and B, staging only):
- [ ] B gets **404** on A's job, candidates, candidate, versions
- [ ] B's job lists (current, queue) never contain A's jobs
- [ ] B gets **404** on A's files: preview, thumbnail, final render, watermark asset/file, with or without B's media token
- [ ] B's write attempts on A's clip/job (PATCH, approve, regenerate, cancel, delete) → 404 and A's data unchanged
- [ ] B's `/api/activity` never shows A's tasks
- [ ] Settings per user; member can't PUT global (admin-only) keys (403/404); no secrets in clear for members
- [ ] Unauthenticated → 401 on every API route; files without session → 401
To add once the API is final: campaigns ownership, per-user API tokens (B's token on A's rows → 404), admin sees all
(activity), login rate-limit, logout invalidates the session, disabled user's session stops working.

## Migration
- [ ] First run: admin from CLIPFLOW_ADMIN_USER/PASSWORD; ALL existing rows assigned to it (counts before = after)
- [ ] CLIPFLOW_API_KEY still works as admin token
- [ ] Worker reads settings for the job owner (user → global → default): render a job as B with B's subtitle default

## Standard (as every gate)
- Fresh-import e2e per active campaign as a member user; Playwright suite + UI vs mock for the login page;
  island and stepper unchanged.
