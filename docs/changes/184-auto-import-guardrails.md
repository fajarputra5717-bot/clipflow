# 184 · Auto-import guardrails, Telegram note, deploy order (2026-10-12)

- Who switched on the first watches (owner asked): `admin`, 22:38:25/26 WIB, browser session from 10.10.10.1
  (Safari/macOS, login 22:38:18), no API tokens on admin, no writes from other IPs → the owner's browser, no incident.
- Guardrails per watch (`source_watches.guardrails` JSONB, `{}` = defaults; `shared/auto_import.normalize_guardrails`
  validates, `describe()` = the UI line): max new jobs per day (2, WIB day, per user × channel; worker counts found +
  imported → "Daily limit (N) reached"), duration 5 min–4 h ("Under 5 min" / "Over 4 h"), title include (≥ 1) /
  exclude (none) keywords (≤ 10, ≤ 40 chars, case-insensitive), pause when free disk < X GB (backend import loop keeps
  the row `found`, "Paused: under X GB free", retries in 10 min, nothing lost), Telegram note per imported job (on).
  The global AUTO_IMPORT_MIN_MINUTES setting is gone (per watch now). A `found` row whose watch was switched off is
  skipped.
- Telegram note: `telegram_sends` kind `note` + `text` column; queued by the import loop to the user's OWN chat
  (`telegram_chat_for`), sent by the sender. Fix: the 141 CHECK only allowed clip|test while 148 inserts `reminder` —
  latent (no planned post had come due yet); the constraint now allows clip|test|reminder|note.
- API: `PUT /api/auto-import/watch` takes `enabled?` and/or `guardrails?` (partial, merged; 400 with the validation
  message); `GET /api/auto-import?campaign=` filter, channels carry `guardrails` + `guard_text`, `disk_free_gb`.
- UI: Campaign page → "Auto-import" box (switch + guard line + Limits form per channel); Auto-import step rows show the
  guard line + "Limits" link to the campaign page.
- Deploy order (CLAUDE.md): backend → worker/sender → frontend; `api()` shows "ClipFlow is updating…" for FastAPI's
  bare "Not Found" (unknown route) and 502/503/504 instead of a raw error box.
- Tests: unittest guardrails (defaults, describe, validation, filters); auto-import.spec (campaign-page Limits save,
  guard line + link, updating message). Phone pill icon-only active step: accepted by the owner.
