# ClipFlow — REBUILD work order (after the 2026-09 VM loss)

**Read this first, then `CLAUDE.md`.** The original VM crashed and its disk
could not be recovered. Nothing had been pushed to git. This repo was
reconstructed from the best copies that survived:

| Part | Source | State |
|---|---|---|
| `backend/app/main.py`, `worker/worker.py`, `frontend/html/index.html` | last full copies shared outside the VM | **Baseline = UI v2.1100**, from *before* the TASKS.md round. Includes: facecam Auto/Left/Right, 6 subtitle animations + live CSS preview, fix-typo preview, new-hook under Edit, manual thumbnail upload, Submagic review-before-render, watermark asset library, version history, per-statement `ensure_schema()`, liquid-glass tab bar. |
| `db/init.sql` | **rebuilt** from every SQL statement in the baseline code | All 73 literal queries + all `ensure_schema()` statements verified to `PREPARE` cleanly against it on Postgres 16. |
| `docker-compose.yml`, Dockerfiles, `requirements.txt`, nginx conf, `.env.example` | **rebuilt** | Include the nginx stale-IP fix, python-multipart, Docker log caps, `additional_contexts: shared`. |
| `docs/tasks/*.md` | original task specs | Full specs; this file says which of them had already landed and must be redone. |

Everything below **R-list** had already been built once, on the lost VM.
Rebuild it in order. The notes under each item are the details that only
came out during the original implementation (bugs found, names chosen).
Those notes beat the original spec wherever they disagree.

## Ground rules (unchanged)

- One task = one commit: `feat(R-NN): …` / `fix(R-NN): …`.
- Each task: `docs/changes/NNN-<slug>.md` + one line in `docs/changes/INDEX.md`
  (template in `docs/tasks/TASKS.md`). Record "what I did NOT verify" honestly.
- Schema only via `ensure_schema()` `statements` list (never edit `db/init.sql`
  for new columns). Settings only via `DEFAULT_SETTINGS`. Candidate updates via
  `update_candidate(...)`. New queues copy the `FOR UPDATE SKIP LOCKED` claim.
- Before each commit: `python3 -m py_compile backend/app/main.py worker/worker.py`,
  `node --check` on the extracted inline script, `docker compose build <svc> && docker compose up -d <svc>`,
  and `curl -fsS localhost/health`.
- Bump the version badge in `index.html` per user-visible change.
- **Never** touch `.env` contents except to add new keys with empty values in
  `.env.example`. **Never** delete the `riftstorm_postgres_data` volume or `/data`.
- You run on the real server. Verify renders by extracting frames
  (`ffmpeg -ss … -vframes 1`) and **looking at them**, not by reading filter strings.
- If Playwright/Chromium can be installed on this VM, use it for UI checks.

## Status legend
- **LANDED**: confirmed built and working on the old VM. Rebuild it.
- **LIKELY**: evidence it landed (seen in the UI) but details unknown. Rebuild from spec, keep it minimal.
- **UNKNOWN**: may or may not have landed. **Ask the user before building.**
- **TODO**: was never done. Leave for after the rebuild.

---

## Rebuild status (2026-09-30): complete except deferred items

| R | Item | Status | Commit(s) | Change doc(s) |
|---|---|---|---|---|
| R-01 | Baseline boots | DONE (+ OpenCV <5 fix: face detection was dead) | 6fefda1, 139c0b9 | 000, 007 |
| R-02 | Runtime settings precedence | DONE | a061467 | 001 |
| R-03 | Auth + CORS + media tokens | DONE | 291fee8 | 002 |
| R-04 | Bigger, centered facecam | DONE | 0587875 | 008 |
| R-05 | Per-job watermark size/opacity | DONE (+ edit-panel style bugs fixed) | c3ce2fb | 009 |
| R-06 | Submagic clean plate | DONE (Submagic upload not run: billable) | 3231a5e | 010 |
| R-07 | Faster analysis | DONE (faster-whisper medium, H.264 ≤1080p) | 6a3652b, 49b8657 | 011 |
| R-08 | Cancel job | DONE (+ Dynamic Island Cancel) | a3a9006, 50d673f | 014 |
| R-09 | Optional burn-in | DONE | bca537f | 015 |
| R-10 | Browser-playable video | DONE (Chromium + WebKit) | 8628d91 | 016 |
| R-11 | UI polish pass | DONE (lane B) | c655474 | 052 |
| R-12 | Left sidebar + simplified Import | DONE (lane B) | b1f5319 | 050 |
| R-13 | Tabs pill + job island | DONE (lane B; superseded by 072/073) | 8b5b599 | 051 |
| R-14 | Disk retention + guards | DONE | 4c24d83 | 017 |
| R-15 | Failure recovery | DONE (approved 2026-09-30) + render watchdog | 7bd2680, b8284b7 | 018, 021 |
| R-16 | One watermark geometry + collision fix | DONE | f4404a9 | 019 |
| R-17 | New default positions | DONE (25 % / 1.5 %) | 331e121 | 020 |
| R-18 | libass spike findings | DONE (lane B) | ef96dcf | 065 |
| R-19 | Display fonts | DONE | 30d78b2, b30dd07 | 064, 013 |
| R-20 | AI provider abstraction | DONE | 15f06be | 004 |
| R-21 | Claude provider | DONE | 2b94832 | 005 |
| R-22 | AI failover policy | DONE | 106e228, 7c20227 | 006 |
| R-23 | Performance feedback | **DEFERRED** (user, 2026-09-30) | | |
| R-24 | Other phase-2 items | **DEFERRED** (user, 2026-09-30) | | |

Also landed outside the R-list: yt-dlp `--` + download retries (253162e, 012), security audit 001 +
URL allowlist/upload re-encode (0ffb8a0, 5d1b7ff; 060, 063), UI-QA badges/chevrons (061, 062), Telegram notifier
(db184d4, c80b887; 066), lane B UX 067–073 (50d673f). Next: TASKS-5 T4 prompt evaluation.

## Phase A — Foundations (do first; everything else depends on them)

### R-01 · Baseline boots · LANDED (already handled in this kit)
`python-multipart` is in `backend/requirements.txt`; without it the backend
crash-loops at import (`Form data requires "python-multipart"`). Just verify
all containers are up, `/health` is healthy, and a job can be created.
Write `docs/changes/000-rebuild-baseline.md` (already drafted) and move on.

### R-02 · Runtime settings: one precedence rule · LANDED (was change 023)
Baseline has **reversed** precedence: worker `setting()` = DB wins, backend
`runtime_setting()` = env wins. Rebuilt behaviour: **both DB-wins**, fall back
to env, then default, with a **5 s in-process cache** in both files.
Also audit for dead settings (keys in `DEFAULT_SETTINGS` that nothing reads,
or code reading `os.getenv` for a key that is in `DEFAULT_SETTINGS`) and wire
them through `setting()`. Update the CLAUDE.md "Runtime settings" section.
Exception: `CLIPFLOW_API_KEY` is env-only (R-03).

### R-03 · Auth + CORS · LANDED (docs/tasks/TASKS-2.md T2, TASKS-4-SECURITY.md T2)
- `X-ClipFlow-Key` header checked by a FastAPI dependency on every `/api/*`
  route except `/health`; `secrets.compare_digest`; 401 uniformly.
- Expected value from env `CLIPFLOW_API_KEY` only (never `app_settings`).
- `allow_origins` from env `CORS_ALLOWED_ORIGINS` (comma list), no `*` with credentials.
- Frontend: prompt once for the key, keep it in `sessionStorage`, send it from
  `api()` **and** the two raw `fetch()` upload calls (thumbnail, watermark).
  `<img>`/`<video>` `src` URLs can't send headers, so decide and document
  how file endpoints authenticate (e.g. short-lived signed query token, or
  leave `GET` file routes open on the LAN) and write the choice down.

---

## Phase B — Work order 1 (docs/tasks/TASKS.md), all LANDED

### R-04 · Bigger, centered facecam · LANDED (T1)
`FACE_ZOOM_RATIO` via `setting()` + `DEFAULT_SETTINGS`, default ~0.78; floor on
the edge clamp (don't shrink below ~60% of requested height; log it); recheck
`max_crop_height`. Auto/Left/Right must keep choosing the correct side.

### R-05 · Per-job watermark size/opacity · LANDED (T2)
`jobs.watermark_width INT`, `jobs.watermark_opacity REAL` (NULL = global default),
edit-panel controls committed via `applyEdits()`; watermark applied **after**
Submagic download in the `applying` branch.

### R-06 · Submagic gets a clean plate · LANDED (T3)
Upload `<candidate_id>_clean.mp4` (no subs, no watermark; cached in PREVIEW_DIR)
instead of the subtitled preview → no double captions.

### R-07 · Faster analysis · LANDED (T4)
Per-stage timing logs first. Download: cap video format to what a 1080×1920
render needs. Normalization must skip non-AV1 sources. Whisper: the old VM
stayed on `openai-whisper` (model from `WHISPER_MODEL`). `faster-whisper` swap
is optional: only if word-level timings survive (karaoke depends on them).
On the new 8-core Ryzen, measure `base` vs `small` vs `medium` and report the
times; let the user pick.

### R-08 · Cancel job · LANDED (T5)
`POST /api/jobs/{id}/cancel`; cooperative checks between stages; terminate
tracked `Popen` for long ffmpeg/yt-dlp; claims must skip `cancelled`; Cancel
button with confirm on running jobs.

### R-09 · Optional burn-in (subtitle-free output) · LANDED (T6)
`jobs.burn_subtitles BOOLEAN DEFAULT TRUE`; `render_vertical(subtitle_path=None)`
skips the filter and keeps label chaining intact; skip `make_ass()` when off;
checkbox "Burn subtitles into video" in the edit panel; reuse the clean-plate path.

### R-10 · Preview video plays in browser · LANDED
The native/ffmpeg preview once failed to play in the browser. Make every
browser-facing mp4: `libx264`, `-pix_fmt yuv420p`, `-profile:v high`,
`-movflags +faststart`, AAC audio; confirm the file endpoint answers HTTP
Range requests (206) through nginx. Test in Safari **and** Chrome.

### R-11 · UI polish pass · LANDED (T7)
Motion 100–200 ms / 300–500 ms, `prefers-reduced-motion`, consistent
loading/disabled states, glass only on drawer + sticky action row.

---

## Phase C — UI shell (from later requests) · LANDED

### R-12 · Apple-Music-style left sidebar + simplified Import · LANDED
Quick actions + Settings in a collapsible **left sidebar** (Workspace →
Quick actions: Refresh import / Refresh queue; Editing tips; Settings
disclosures: Advanced settings · system/publishing, Watermark · asset
library, Performance · leaderboard & correlations). Import form simplified.
Fix the regression we hit once: after the move **nothing was clickable**
(an overlay/stacking layer swallowed clicks). Check `pointer-events` and
`z-index` of every fixed/overlay layer.

### R-13 · Tabs pill + separate job island · LANDED (TASKS-UI-QA T1–T3)
- `docs/changes/ui-audit.md` inventory first (T1).
- Tabs bar docks into a pill on scroll: animate **only transform/opacity**,
  cross-fade children, asymmetric durations, `will-change` only during the
  transition, hysteresis ~64/48 px. It shipped once with a jerky
  bar-to-pill morph and a conflict between two scroll handlers. **One**
  scroll handler owns the state.
- Job status island is its **own** capsule (not merged into the tabs pill),
  appears only while a job runs, shows stage + %, animates independently.

---

## Phase D — Reliability (docs/tasks/TASKS-2.md P0)

### R-14 · Disk retention + guards · LANDED (T1) — includes the incident fixes
The old disk hit 100% and corrupted a Postgres recovery. Rebuild with:
- Idle-time sweep of intermediates (downloads, audio, normalized, clean plates)
  older than `RETENTION_DAYS_INTERMEDIATE` (3). **Eligibility bug found once:**
  a job is eligible only when **all** its candidates are terminal
  (`completed`/`cancelled`/`failed`). Never delete finals or thumbnails.
- Orphan sweep behind `ORPHAN_SWEEP_DRY_RUN` (default **true**, log only).
- `DISK_SPACE_MIN_MB`: refuse new analysis jobs below it (clear message),
  plus **mid-pipeline** checks before download/normalize/render.
- yt-dlp **pre-flight size check** (`--print filesize_approx` or `-j`) and
  refuse with **HTTP 507** if it won't fit.
- Show free disk space in the settings sidebar.

### R-15 · Failure recovery · DONE (approved 2026-09-30; was UNKNOWN (T3))
Heartbeat + stale-claim reclaim, Retry button, transient vs permanent errors.
(`shared/errors.py` from R-19 already gives the classifier.)

---

## Phase E — Video output (docs/tasks/TASKS-4-VIDEO.md)

### R-16 · One watermark geometry + collision fix · LANDED (VIDEO T1)
- `get_watermark_rect(job, canvas, asset)` is the **single** source of watermark
  x/y/w/h; ffmpeg overlay and `make_ass()` margins both read it.
- **Use the PNG's alpha bounding box**, not its canvas size. The real asset
  (the `instgrm : @motion.klip` mark) is a **full-canvas transparent PNG**, and the
  global `WATERMARK_WIDTH` was **320**, not 630. Using canvas size put the
  computed rect in the wrong place and pushed captions into the facecam.
- Caption collision uses the caption **top** edge
  (`H - margin_v - est_text_height`); resolve deterministically, log it.
- The seam floor may only **increase** margin (never let a clamp push captions
  below the seam into the facecam at 60:40).
- Verify at **60:40 and 70:30**, `hormozi` preset, 3-line caption, by extracting frames.

### R-17 · New default positions · LANDED (VIDEO T2)
`WATERMARK_POSITION_Y` (percent, ~20–30%) and a subtitle seam-gap/offset
setting; captions sit closer to the seam but never cross it; existing jobs
with stored positions unchanged.

---

## Phase F — Native caption quality (docs/tasks/TASKS-3.md)

### R-18 · libass spike findings · LANDED (T0): just record them
Write the change-log entry from these known results (re-verify quickly):
per-word `{\c}` colour works alongside `\kf`; rounded padded boxes are viable
via `\p1` drawings as a separate event behind text; per-word `\t` works;
**colour emoji does not render in libass → emoji feature dropped** (T4 skipped).

### R-19 · Display fonts · LANDED (T1)
SIL-OFL fonts (verify each licence; ship OFL.txt): Anton, Bebas Neue,
Montserrat (Bold/ExtraBold/Black), Poppins (Bold/ExtraBold), Oswald,
Inter (Bold/Black), Archivo Black → `worker/fonts/` (the Dockerfile copies it
to `/usr/share/fonts/truetype/clipflow/` + `fc-cache`). Get them from the
google/fonts GitHub repo (`ofl/<family>/`). Use the exact family names from
`fc-list : family style`. **Font-selection bug found once:** the chosen font
didn't reach the ASS `Style:` line (a normalizer fell back to the default).
Trace UI → PATCH → `jobs.subtitle_style` → `normalize_subtitle_font()` → `make_ass()`
and render every font to a frame to confirm. Dropdown shows each option in
its own typeface.

---

## Phase G — AI provider failover (docs/tasks/TASKS-5-AI-PROVIDER.md) · LANDED T1–T3

These are the names actually used (they differ from the spec, keep these):

### R-20 · Provider abstraction (T1, separate commit, no behaviour change)
`shared/ai/router.py`, `shared/ai/gemini.py`, `shared/ai/claude.py`,
`shared/errors.py` (`classify_exception()`, `is_transient_gemini_error()`,
`AITransientError` / `AIPermanentError`). `shared/` is copied into both images via
compose `additional_contexts` (already wired in this kit). All call sites go
through one `ai_generate_json(prompt, schema, *, task, max_tokens)`.

### R-21 · Claude provider (T2)
Messages API, **forced tool-use** for structured output
(`tool_choice={"type":"tool","name":...}`); unwrap `{"clips":[...]}`.
Settings: `ANTHROPIC_API_KEY` (secret), `CLAUDE_MODEL_ANALYSIS=claude-sonnet-5`,
`CLAUDE_MODEL_UTILITY=claude-haiku-4-5-20251001`. Check the model IDs against
Anthropic's docs when you build this.

### R-22 · Failover policy (T3)
`CLIP_ANALYSIS_PROVIDER` / `TEXT_UTILITY_PROVIDER` ∈ `gemini|claude|auto`;
fail over on transient errors only; backoff with jitter; circuit breaker
**3 consecutive failures → 60 s cooldown**; `clip_candidates.hook_provider`
records who produced each hook; log every failover.

---

## Phase H — Growth features

### R-23 · Performance feedback · DEFERRED (was LIKELY, TASKS-2 T4)
The sidebar had "Performance · leaderboard & correlations". Needs YouTube
OAuth (client id/secret/refresh token) + YouTube Analytics API.
`clip_performance` table, scheduled pull, leaderboard sorted by retention/CTR,
honest "sample too small" messaging. **Ask the user** whether it was wired
to real analytics or UI-only before building the fetcher.

### R-24 · Other phase-2 items · DEFERRED (was UNKNOWN)
TASKS-2: T5 retention editing (silence trim, loudnorm −14 LUFS, punch-in),
T6 platform safe zones, T7 hook prompt quality, T8 SSE, T9 batch, T10 edit-panel IA.

---

## Not done before the crash (TODO, after the rebuild)

- TASKS-3 T2 keyword highlighting (**Indonesian stoplist**), T3 presets, T5–T7.
- TASKS-5 T4 prompt evaluation Gemini vs Claude, T5 AI settings UI.
- TASKS-4-VIDEO T3 manual position editor.
- TASKS-UI-QA T4–T7 (job-card thumbnails, one chevron affordance, badges, a11y).
- TASKS-4-UIUX (its Task 2 browser harness first), TASKS-4-SECURITY (audit first).

## Suggested session plan
1. R-01 → R-03 (one session). 2. R-04 → R-11. 3. R-12 → R-13.
4. R-14 → R-17. 5. R-18 → R-22. 6. Ask about R-15, R-23, R-24.
After each session: `git push` (private remote), confirm the nightly DB backup exists.
