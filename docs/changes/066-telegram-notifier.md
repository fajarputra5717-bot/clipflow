# 066 — Telegram notifier service (rebuild of the lost alerts)
Date: 2026-09-29 · Commit: see `git log --grep "notifier"` · Files: notifier/{Dockerfile,notifier.py,requirements.txt,compose-snippet.yml}

## What changed
New standalone `notifier` service (python:3.12-slim, psycopg + requests). worker.py, main.py and docker-compose.yml
are untouched. Lane A pastes `notifier/compose-snippet.yml` under `services:` at merge.
- Every `POLL_SECONDS` (30) it reads Postgres in a **read-only session** (`default_transaction_read_only=on`, 15 s
  statement timeout), GETs `http://backend:8000/health` and checks free space on `/data`.
- Alerts: job ready for review (title + clip count); final render done (`completed` + `final_path`); job
  `failed`/`partial_failure` and clip `failed` (stage + scrubbed error, ≤300 chars); hooks with `hook_provider =
  'claude'` ("Gemini overloaded, Claude used", once per job, skipped when `CLIP_ANALYSIS_PROVIDER` is set to `claude`
  in app_settings); backend /health failing ≥2 polls in a row and recovered; disk free < `DISK_ALERT_PCT` (15) and
  recovered (re-arms at +2 points); a daily summary at `SUMMARY_HOUR` 08:00 WIB (fixed UTC+7) covering jobs
  done/failed, clips rendered, clip failures and disk free.
- Dedupe: sent keys (`review:<job>:<ts>`, `final:<cand>:<rendered_at>`, `jobfail:…`, `candfail:…`, `fallback:<job>`)
  plus health/disk/summary flags live in `/data/notifier/state.json`, written atomically and pruned after 30 days.
  **The first run with no state file baselines**: everything already in the DB is marked seen, nothing is sent.
  Only rows updated in the last 48 h are considered.
- Hourly cap `MAX_PER_HOUR` (20, sliding). Over the cap, events stay pending and go out on later polls (nothing is
  lost or marked sent). Telegram 429 `retry_after` is honoured.
- `python notifier.py --send-summary` sends one summary now.

## Security decisions
- **Outbound only:** it never calls `getUpdates`, has no webhook and no listening port, so there is no bot command surface.
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` are env-only. If unset, it logs once and idles. The token is never logged:
  request exceptions log only their type, since `str(exc)` contains the URL with the token.
- `scrub()` covers every error text and every log line. It redacts Telegram bot tokens, `AIza…`/`sk-…` keys,
  Bearer/Basic credentials, `*key*|*token*|*secret*|*password*|sig|auth = value`, `user:pass@` in URLs, URL query
  strings/fragments (`?[…]`) and any 40+ char opaque string.
- Container (snippet): non-root uid 10001, `read_only: true` rootfs + tmpfs `/tmp`, `cap_drop: ALL`,
  `no-new-privileges`. `/data` is read-only. `/data/notifier` is bind-mounted writable on top: the spec's
  "/data read-only" and "state in /data/notifier" only combine this way. It only gets the app env (DATABASE_URL), not
  the provider keys.
- Not done: a dedicated read-only Postgres role. The session is read-only, but a role would enforce it server-side.
  Suggested for Lane A: `CREATE ROLE notifier LOGIN PASSWORD …; GRANT SELECT ON jobs, clip_candidates, source_videos,
  app_settings TO notifier;` plus its own DATABASE_URL.

## Deploy (Lane A)
`mkdir -p /data/notifier && chown 10001:10001 /data/notifier && chmod 700 /data/notifier` (already done on this
host; the dir exists empty). Paste the snippet, then `docker compose up -d --build notifier`. The first start
baselines silently.

## Verification (2026-09-29, this host)
- `docker build` OK.
- Offline self-test in the image (`--network none`, fake transport): 7 scrub cases, including a signed googlevideo
  URL, `key=AIza…`, `Bearer sk-…`, a postgres URL with a password, the Telegram bot URL and a JSON `x-api-key`. With
  a cap of 3/h, 3 sent then 0, and the rest sent after the window rolled. After a restart, no resend.
- Live: `docker run --rm` on `riftstorm_default` with the POSTGRES_*/TELEGRAM_* values from .env (filtered env file,
  deleted afterwards), `/data:ro`, `/data/notifier` rw, `--read-only --cap-drop ALL`, `POLL_SECONDS=5`,
  `NOTIFIER_TAG="[TEST] "`. It baselined 7 existing events and sent none. Then a TEST job
  (`test-notifier-066`, no source video, so the worker can't claim it) went through processing → review
  (3 clips, 2 `claude`) → clip 1 completed, clip 2 failed with a fake key + signed URL → job failed with a fake token +
  Bearer. Telegram accepted all 5 (message_id 1636–1640), and the failure texts came out scrubbed (`?[…]`,
  `key=[redacted]`, `Authorization: [redacted] [redacted-key]`). A restart with a 404 health URL and
  `DISK_ALERT_PCT=101` sent disk-low (1641) and health-down after 2 checks (1642), with no resend of the 5. A restart
  with normal settings sent recovered (1643) and disk OK (1644). `--send-summary` sent 1645.
- Cleanup: TEST job + 3 candidates deleted (0 left), test state.json removed, test image removed.
- NOT verified: that the messages look right in the Telegram client (only API `ok` + message_id were checked); the
  real 08:00 WIB trigger (logic only, the summary was forced); a real backend outage; compose integration.
