# 211 · FastAPI docs off in production (deep audit L10, 2026-10-14)

`/docs`, `/redoc` and `/openapi.json` answered without auth on the backend's :8000 (127.0.0.1 only; via nginx they fall
back to index.html): they list every route if :8000 is ever exposed. `FastAPI(docs_url/redoc_url/openapi_url=None)`
unless `CLIPFLOW_ENV` (env-only) is set to something other than production. Production has it unset → all three off;
staging (`CLIPFLOW_ENV=staging`) keeps them for QA's unauthenticated route sweep. Checked by importing the app with the
env unset (None, None) and with staging (/docs, /openapi.json).
