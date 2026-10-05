# QA review · b7f895b (lane-b) · staging stack (clipflow-staging, 8080/8001)
Reviewer: Lane C · 2026-10-05 · stack is up (8080 → 200, 8001/health → 200, 4 containers).
Isolation verified live: own compose project + own Postgres volume; production /data mounted **read-only**, writes
only to /data-staging; Whisper cache ro; backend bound to 127.0.0.1:8001; `restart: "no"`; worker 2 CPUs; no
`riftstorm-*` writes. `.env.staging` mode 600; Telegram/Submagic keys empty in env, none stored in staging's
app_settings → no billable Submagic exports or real Telegram sends from staging. AI keys (Gemini/Anthropic) are
live: staging analyses cost real AI calls (expected; keep staging jobs few).
Findings: Low · frontend port 8080 binds 0.0.0.0 (all interfaces) like production :80; fine on this VM, note for
exposure. **Merge: OK** (infra only; no app code).
