# 140 · Distinct session cookie on staging (CLIPFLOW_ENV) · app/auth.py, shared/settings.py, .env.example

Lane C Low (P1.5 gate): cookies are host-scoped (not port), so production (:80) and staging (:8080) on one box shared
`clipflow_session` and logged each other out. New env-only `CLIPFLOW_ENV` (default production): production keeps
`clipflow_session` (no logouts); any other value → `clipflow_<env>_session` (staging: `clipflow_staging_session`).
Staging must set `CLIPFLOW_ENV=staging` in `.env.staging` (Lane B: then drop your own cookie-name patch).

**Verified:** image import with/without the env → `clipflow_session` / `clipflow_staging_session`; prod login
Set-Cookie `clipflow_session` (HttpOnly, SameSite=Lax) after deploy.
