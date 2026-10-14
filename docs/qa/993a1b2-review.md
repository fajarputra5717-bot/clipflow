# prod 993a1b2 (merge of sfx-library 13df828, 217) — post-deploy check, read-only

- Containers: backend 05:50:17, worker/sender 05:50:34, frontend 05:50:35 UTC (order as announced); all riftstorm-* restarts=0 (pot, notifier, postgres untouched). No "error"/traceback in backend or worker logs since the deploy.
- Backend: ffmpeg 5.1.9 present; image 1.04 GB; disk 15 % used (318 GB free); `sfx_assets` empty. `/docs` and `/openapi.json` still 404.
- Routes unauthenticated: `/api/sfx`, `/api/sfx/<id>/file`, `/api/sfx/freesound/search` → 401 on :8000 and via nginx.
- Static built-ins: `/sfx/ding.wav` 200 `audio/wav`; `/sfx/laugh.wav` 404 (laugh has no bundled recording, by design); path traversal `/sfx/../../etc/passwd`, `..%2f` and `%2e%2e` (sent as-is) → 400, directory `/sfx/` → 403 (no listing).
- Not verified on prod: an upload/render with the library (no prod QA account; owner decision), Freesound (no key).

Result: PASS, no findings.
