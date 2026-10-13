# hardening 1c82c7a (209–212) on staging — re-check

Staging = hardening 1c82c7a (note: unlike c6bcda4, this one changes `backend/app/main.py`: the auth middleware keeps its DB connection for `/api/activity`, so I re-ran the cross-user sweep).

| Item | Result |
|---|---|
| 210 (205 Low 1) `.rv-seg` pressed | PASS: "To review" pressed = accent + white in light (rgb(0,113,227)) and dark (rgb(0,102,204)); unpressed transparent. The Pick list shows the same control |
| 209 (M6) deploy gap | PASS (nginx + app): a throwaway nginx (staging conf, no backend, own network, removed afterwards) answers `/api/jobs` GET and POST with `503` + `Content-Type: application/json` + `Retry-After: 5` + `{"detail":"ClipFlow is updating… try again in a minute."}`; the index page still 200. Frontend with mocked 503 on `/api/publish-queue`: GET retried at 0.4 s, 1.4 s, 3.9 s (≈1 / 2.5 s gaps), then succeeded and the page loaded with no error; a `PUT /api/review/filter` answered 503 was sent once (writes not retried). I did NOT stop the staging backend (Lane C does not stop containers); the compose journald logging applies to prod only and is not checked |
| 211 (L10) docs off in prod | PASS by code + env: docs/redoc/openapi are on only when `CLIPFLOW_ENV` ≠ production, default production; the prod backend has no `CLIPFLOW_ENV` set, so it defaults to production (docs off once deployed); staging keeps them (200 on :8001). Prod itself still serves them until deployed |
| 212 (L11) | PASS: `idx_user_sessions_expires` exists on staging; `/api/activity` p50 16 ms / p95 17 ms over 200 calls (was 23/25), no connection growth (1 → 1), 0 idle-in-transaction, unauthenticated still 401. Transactions per call measured 3 incl. worker/notifier background polling (claimed 1 for the request); not isolated further |
| Cross-user re-sweep | PASS: same 90 operations as lane-c-b → lane-c-a: 52×404, 9×403, 26×200 (own/shared), 1×400, 1×409, 1×422; identical to the a26b041 run; the 6 DELETEs are still not run |

## Findings
None.

## Not verified
Live backend-down deploy gap (not stopping staging); prod journald logging; docs-off on a real production-env backend; the 6 DELETE operations in the sweep.

Merge: OK for 209–212 (with 202–208 already checked).
