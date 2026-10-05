# Incident 2026-10-05 · qa-multiuser.spec.js run against production
What: Lane A ran the spec against production; user B's settings write attempt set WHISPER_MODEL=tiny (restored by Lane A).
Findings:
1. **HIGH · a member can write global (admin-only) settings** (`PUT /api/settings`). The spec caught a real P1.5 gap:
   global keys (AI keys, Whisper, disk) must be admin-only (403/404 for members). Open until Lane A's settings part lands.
2. **Process · the spec had no environment guard.** Fixed in QA: it now throws unless the base URL is staging
   (localhost:8001/:8080), verified (`:8000` → "REFUSES to run"; `:8001` → proceeds). The write attempt re-sends the
   current value, so it can't change behaviour even when the guard is missing.
