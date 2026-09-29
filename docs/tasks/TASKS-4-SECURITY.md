# ClipFlow — stream: SECURITY

Segmented task stream. Companion streams: `TASKS-4-VIDEO.md`,
`TASKS-4-UIUX.md`.

Read `CLAUDE.md` and `docs/changes/INDEX.md` first.

**Scope and standard:** this is a self-hosted app on a LAN-reachable
host with no public HTTPS. Test against **OWASP ASVS Level 1** plus the
relevant **OWASP Top 10 (2021)** categories. Level 1 is the honest bar
for this deployment — don't pad the report with L2/L3 findings that
don't apply, and don't claim compliance with a standard you only
partially tested.

**Rules of engagement:** test only against the user's own local
instance. No scanning of Submagic, YouTube, Gemini or any third party.
Don't commit real credentials, tokens, or captured request bodies into
`docs/` — redact before writing anything down.

Ground rules unchanged: one task = one commit, `docs/changes/NNN` +
INDEX line, compile checks, honest verification notes.

---

## Task 1 — Threat model + audit report (no code changes)

Produce `docs/security/audit-001.md` **before** fixing anything. For
each finding: severity, ASVS/Top-10 reference, concrete reproduction,
and the actual impact **on this deployment** — not a generic textbook
description. Rate severity by real exploitability here, not by CVSS
copied from a template.

Cover at minimum:

1. **Authentication.** There is none. Every `/api/*` route is
   unauthenticated. Enumerate exactly which routes cause damage when
   called by anyone who can reach the host: job deletion, Gemini spend,
   Submagic export (**real money**), YouTube upload, settings read.
2. **CORS.** `allow_origins=["*"]` with `allow_credentials=True` —
   check whether that combination is actually in force, and what it
   exposes given there's no auth to steal.
3. **Secrets exposure.** `GET /api/settings` serves the settings table.
   Confirm what `SECRET_SETTING_KEYS` actually masks and whether any
   key path leaks a real value. Check whether secrets appear in logs or
   in error responses.
4. **File upload.** Two `UploadFile` endpoints (thumbnail, watermark).
   Test: content-type spoofing, path traversal in `filename`, zip/
   decompression bombs, oversized files, SVG-with-script, and whether
   an uploaded file can land outside `DATA_ROOT`.
5. **File serving.** The candidate-file and watermark-file endpoints
   build paths from DB values. Test for traversal and for reading
   arbitrary files off the host.
6. **SSRF.** `videoUrl`/YouTube URL inputs get fetched server-side by
   yt-dlp. Test whether internal addresses (`127.0.0.1`, `169.254.169.254`,
   LAN hosts) can be reached through it.
7. **Command injection.** Every `run_command()` call site. Confirm
   argument-list form is used everywhere and no user-controlled string
   reaches a shell. **Pay specific attention to the ASS subtitle path
   escaping in the `subtitles=` filter** — that one builds a filter
   string by concatenation and only escapes `'`.
8. **SQL injection.** The dynamic-field builders (`update_candidate`,
   the PATCH endpoint's `fields`/`values` construction). Confirm column
   names are never user-controlled and values are always parameterised.
9. **Rate limiting / DoS.** None exists. A retry loop on the AI
   endpoints spends real money; unbounded job creation fills the disk.
10. **Dependency audit.** `pip-audit` (or `safety`) on both images.
    Report CVEs with a real path to exploitation here, separately from
    noise.

---

## Task 2 — Authentication + CORS

Implement the P0 from `TASKS-2.md` if it hasn't landed:

- Shared-secret header (`X-ClipFlow-Key`) via a FastAPI dependency on
  all `/api/*` except `/health`. Compare with `secrets.compare_digest`,
  not `==`.
- **The expected value lives in an environment variable, never in the
  `app_settings` table** — that table is served over the API, so
  storing the key there makes it readable through the thing it
  protects.
- Lock `allow_origins` to a configurable explicit origin list.
- Frontend sends the header on `api()` and on the raw `fetch()` upload
  calls. Prompt once, hold in `sessionStorage`.
- Return 401 consistently; don't leak whether a route exists.

---

## Task 3 — Input validation + upload hardening

From the Task 1 findings. Expected work:

- Validate uploads by **magic bytes**, not the client-supplied
  content-type. Re-encode images through Pillow (already a dependency)
  rather than trusting input. Reject SVG.
- Generate stored filenames server-side; never use the client's
  `filename` in a path.
- Enforce size limits **while streaming**, not after reading the whole
  body into memory.
- Resolve every constructed path and assert it is inside `DATA_ROOT`
  (`Path.resolve()` + `is_relative_to()`), on both write and read.
- Validate the YouTube URL against an allowlist of hosts before it
  reaches yt-dlp.
- Bound every numeric input from the new position controls
  (`TASKS-4-VIDEO.md` task 3) server-side, not just in the UI.

---

## Task 4 — Rate limiting + spend guards

- Per-route limits on the paid paths: Gemini hook/typo/thumbnail,
  Submagic export, YouTube upload.
- A hard daily cap on billable Submagic exports, configurable, that
  refuses rather than queues when exceeded. This is the one that
  protects actual money.
- Exponential backoff with a ceiling on worker-side retries.
- Cap concurrent analysis jobs and refuse new ones below a disk
  threshold (overlaps `TASKS-2.md` task 1 — check whether that landed
  before duplicating it).

---

## Task 5 — Re-test and close out

Re-run every reproduction from Task 1. Update `docs/security/audit-001.md`
with the resolved status per finding.

**Be explicit about what remains open and why.** A finding deliberately
accepted (e.g. "no TLS — LAN-only deployment, accepted") is a valid
outcome; silently dropping it from the report is not. If a fix is
partial, say which part.

---

## Order

Task 1 (audit) → 2 (auth) → 3 (validation) → 4 (limits) → 5 (re-test).

Do not skip Task 1. A security pass where the fixes precede the
findings is just a feature list.
