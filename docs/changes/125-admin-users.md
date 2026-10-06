# 125 · P1.5 part 5: admin Users section (create, disable/enable, role, reset password), forced password change, last-admin guard · app/auth.py, main.py, index.html

- **`users.must_change_password`**: set by an admin create or reset (temporary password). Such a session may only call
  `/api/auth/me` and `/api/auth/password` (middleware 403, `code: password_change_required`) until it picks its own;
  the change clears the flag. Login and `/api/auth/me` return `must_change_password`.
- **Endpoints (admins only; the middleware 403s `/api/admin/*` for members):** `GET /api/admin/users` (role, active,
  temp-password flag, jobs, tokens, last seen), `POST /api/admin/users` {username, password ≥ 12, role} (409 if taken;
  username 2-32 of a-z 0-9 . _ -), `PATCH /api/admin/users/{id}` {active?, role?}, `POST …/{id}/reset-password`.
  No signup route.
- **Disable** ends every session and DELETES the user's API tokens (re-enable doesn't bring them back). **Reset**
  signs the user out everywhere and forces a change; tokens are kept (revoke or disable for a compromised account).
- **Last admin:** disable/demote of the last active admin → 409 ("Make another admin first"), for yourself or
  anyone. Active admin rows are locked `FOR UPDATE` so two concurrent changes can't both pass.
- **UI:** Settings sheet → "Users" (admins only; hidden by a search that doesn't match): rows with role/Disabled/
  Temporary password tags, two-step Disable, Make admin/member, Reset password (inline field + Generate), Create
  user (username, temporary password + Generate, role). Login layer: after an admin-set password, "Choose a new
  password" (the temporary one isn't asked again right after sign-in; asked after a reload). Errors inline.
- `CLIPFLOW_API_KEY` stays (= bootstrap admin) until the P1.5 gate passes on staging and the owner confirms removal.

**Verified:** production (read-only): admin list = [admin, admin, active, 24 jobs], anonymous `/api/admin/users`
401, `/api/auth/me` carries `must_change_password`, no signup route (401 like any unknown path). Harness 52 passed
(+ users.spec: create/validation/Generate, last-admin 409 inline, two-step disable, reset; member never sees or calls
Users; forced change before the app opens). Write checks (member 403, disable kills sessions + tokens, reset → forced
change, last-admin 409 live) go to the staging run with parts 1–4.
