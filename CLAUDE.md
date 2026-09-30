# ClipFlow — agent context (read this first, don't re-crawl the repo)

> **REBUILD IN PROGRESS.** The original server was lost (2026-09). This repo
> starts from the v2.1100 baseline. Work through `REBUILD.md` in order;
> it lists every feature that existed before and must be rebuilt, with the
> gotchas learned the first time. Update this file as invariants change.

## Layout (this server: /opt/clipflow, VM on Proxmox)

```
docker-compose.yml   project name "riftstorm" → volume riftstorm_postgres_data
.env                 secrets (gitignored; never print, never commit)
db/init.sql          base tables, runs once on an empty volume
backend/app/main.py  FastAPI  (container riftstorm-backend, :8000, 127.0.0.1 only)
worker/worker.py     worker   (riftstorm-worker; face model in /app/models, Whisper in hf_cache volume, fonts in worker/fonts)
frontend/html/       index.html served by riftstorm-frontend (nginx :80)
frontend/conf.d/     nginx conf (dynamic resolver, see comments)
shared/              python package copied into backend+worker images at /app/shared
docs/changes/        change log (INDEX.md + NNN-*.md)
docs/tasks/          original task specs
/data                media on the data disk (bind-mounted into backend+worker)
```

Rebuild/restart one service: `docker compose build worker && docker compose up -d worker`.
Frontend changes need no rebuild (directory bind mount); hard-refresh the browser.
Logs: `docker compose logs -f --tail=200 worker`.
DB shell: `docker compose exec postgres psql -U clipflow -d clipflow`.

**Change history lives in `docs/changes/`, not here.** Read
`docs/changes/INDEX.md` (one line per change) and open a detail file
only when you need the reasoning behind something you're about to
touch. This file is condensed *invariants* — how the system works
now. When you change an invariant, update it here AND write a new
`docs/changes/NNN-<slug>.md` entry.

Auto-clipper: YouTube long-form → vertical Shorts/Reels/TikTok, with
AI hook selection, animated burned-in subtitles, AI + manual
thumbnails, an optional Submagic pass, and a watermark asset library.

**3 app files, no framework magic:**
- `main.py` — FastAPI API. Owns the DB schema (`ensure_schema()` at
  top: idempotent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` /
  `CREATE TABLE IF NOT EXISTS`, one line per historical change — this
  IS the migration log, read it before assuming a column exists).
  Also does short synchronous AI calls (Gemini fix-typo/description,
  runtime settings CRUD).
- `worker.py` — polling background processor. `main()`'s loop claims
  work in priority order: native candidate task → analysis job →
  Submagic task → Submagic poll → sleep(2). Every long-running job
  (download, transcribe, Gemini analysis, ffmpeg render, Submagic
  upload/export) lives here, never in an API request handler.
- `index.html` — single-file frontend (vanilla JS, no build step).
  Event handling is delegated (`document.addEventListener("click"/…)`
  with `data-*` attributes), not per-element listeners. Grep for
  `data-yourthing` to find both the button markup and its handler.

## State machines (two independent ones per candidate — don't conflate)

- `clip_candidates.status` (native pipeline): `queued` →
  `preview_queued`→`preview_rendering`→`review` →
  `render_queued`→`rendering`→`completed`, or `thumbnail_queued`→
  `thumbnail_rendering`. Claimed via `claim_candidate_task()`
  (`FOR UPDATE SKIP LOCKED`, same pattern everywhere a queue is
  claimed — copy it for any new queue instead of inventing one).
- `clip_candidates.submagic_status` (optional, opt-in, parallel):
  `NULL/failed/applied` (resting) → `queued_upload`→`uploading`→
  `transcribing`→`transcribed` → `queued_export`→`exporting`→
  `completed` → `queued_apply`→`applying`→`applied`. Never touches
  `status`/`final_path` until the explicit `use-as-final` step.

## Failure recovery (R-15)

Claimed rows carry `heartbeat_at` (CancelWatch, 30 s); `reclaim_stale()`
(startup + idle every 60 s) requeues orphaned/stale claims with
`attempts+1`, failing at `JOB_MAX_ATTEMPTS`. Stage failures go through
`record_failure()`: `shared/errors.failure_class()` → transient =
requeue with `retry_after` backoff (claims must keep the `retry_after`
filter), permanent = `failed`. A new failure path: call
`record_failure`, don't hand-write `status='failed'`. Manual retry:
`POST /api/jobs/{id}/retry`, `.../candidates/{cid}/retry`.
Renders run with a watchdog: `run_command(..., timeout=render_timeout_seconds(duration))`
(max 300 s, 10× clip); timeout → `RenderTimeout` (transient). New ffmpeg render → pass a timeout too.

## Disk (R-14)

Reserve `DISK_SPACE_MIN_MB`: `ensure_disk_space(stage, need_mb)` before
download/normalize/every render (new heavy step → call it too);
`POST /api/jobs` answers 507 below it. Idle sweeps in `main()`:
retention deletes intermediates **per source video** (all jobs +
candidates terminal, older than `RETENTION_DAYS_INTERMEDIATE`), marks
it `purged`; orphan sweep is dry-run unless `ORPHAN_SWEEP_DRY_RUN=false`.
Never sweep finals/thumbnails. New file kinds: name them with the job or
candidate id (or store the path in the DB) or the orphan sweep flags them.

## Cancellation (R-08)

`POST /api/jobs/{id}/cancel` sets `cancelled`; the worker's
`CancelWatch` (2 s DB poll) kills the running subprocess and raises
`JobCancelled` at the next `check_cancelled()` (stage boundaries, each
Whisper segment, after `run_command`). New long-running code: go
through `run_command`, call `check_cancelled()` in loops, and put
`except JobCancelled: raise` before any broad `except Exception`.
`update_job`/`update_candidate` never overwrite a cancelled row.

## Subtitle style — dual storage, don't forget either half

`jobs.subtitle_style` JSONB = `{style, font, size, animation, bold,
color, outline, position}` is the source of truth read by
`make_ass()`. `jobs.subtitle_font` / `subtitle_size` /
`subtitle_animation` are *denormalized copies* of the same values in
their own columns (query convenience). `normalize_subtitle_style()`
in main.py and `normalize_subtitle_style()` / `normalize_subtitle_
font/size/animation()` in worker.py all merge-and-default this — when
adding a new style key, update the dict default AND both files' merge
functions AND the INSERT/UPDATE column lists in main.py.

Color/weight ("style": bold/outline/clean/boxed/hormozi/neon/minimal/
impact/pastel/gold) and motion ("animation": karaoke/word_pop/bounce/
fade_settle/typewriter/none) are fully decoupled — any style pairs
with any animation. Both are real ASS override tags baked into the
exported video by `make_ass()` in worker.py, not CSS-only preview
fluff. The frontend's `SUBTITLE_STYLE_PREVIEW` / `SUBTITLE_ANIMATIONS`
in index.html are a *hand-maintained mirror* for the live CSS
preview — keep them in sync manually if you change the ASS side.

## Transcription (R-07)

faster-whisper (int8, CPU) via `whisper_model()` / `transcribe()` in
worker.py; model = `WHISPER_MODEL` setting (default medium; this box
has it as an app_setting because `.env` pins base). Models live in the
`hf_cache` volume (`HF_HOME=/cache/huggingface`). `transcribe()` must
keep returning per-word `{word,start,end}`: karaoke depends on it.
Every analysis stage is timed (`StageTimer`, one summary log line).

## Caption fonts (R-19)

`shared/fonts.py` `CAPTION_FONTS` is the whitelist (backend normaliser
+ worker `make_ass()`); index.html mirrors it by hand. Display fonts
select weight by name ("Montserrat Black") with ASS Bold=0 — never add
`\b`/Bold on top (libass faux bold). Unknown font → default + log line.
Captions strip emoji (libass can't draw them). Files: `worker/fonts/`,
also served to the browser at `/fonts/` (nginx alias).

## Facecam layout hint

`jobs.layout` ∈ `auto|left|right`, set once at job creation (Import
form choice-grid), read by `detect_face_for_clip(..., layout=...)` in
worker.py to bias corner-scoring and the no-face fallback position.
Threaded through 3 call sites: `create_preview`, `render_final_
candidate`, `generate_ai_thumbnails` — plus `claim_candidate_task`'s
SELECT and the `job` dict built in `process_candidate_task`. If you
add a new render/detection call site, thread it there too or it
silently falls back to `"auto"`.

## Thumbnails

`clip_candidates.thumbnail_options` (JSONB array of paths, relative
to `DATA_ROOT`) holds AI-generated options *and* manually uploaded
ones (`POST .../thumbnail-upload`) in the same list — indistinguishable,
picked the same way. `thumbnail_locked` (bool) is the load-bearing
flag: once a thumbnail is explicitly picked (`update_candidate` PATCH
`selected_thumbnail_index`), `create_preview()` / `render_final_
candidate()` in worker.py check it before overwriting `thumbnail_path`
with a freshly-extracted frame. **Any new code path that regenerates
a preview/final render must respect `thumbnail_locked` or it will
silently revert the user's thumbnail choice** — this was a real bug,
fixed once already.

## Watermark

`WATERMARK_PATH` (`/app/assets/watermark.png`) is the baked-in
fallback only. The real source of truth is `watermark_assets` table +
`ACTIVE_WATERMARK_ID` app_setting, resolved fresh per render by
`resolve_watermark_path()` in worker.py — never read `WATERMARK_PATH`
directly in new code, call the resolver.

Geometry (R-16): `get_watermark_rect()` is the only placement logic
(alpha-bbox crop; `WATERMARK_WIDTH` = visible mark width at 1080).
`make_ass()` returns the rect after clearing the caption top edge (the
watermark moves up; captions never go below the seam) and the render
must use that same rect via `render_vertical(watermark_rect=…)`.
Positions (R-17): `jobs.watermark_position_y` / `subtitle_seam_gap` are
snapshotted from settings at job creation; `job_layout(job)` → NULL =
legacy 50 % / 4 %. Pass its values to make_ass/get_watermark_rect.
Burn-in toggle (R-09): `jobs.burn_subtitles` (NULL = on, `job_burn_subtitles()`); off = no `make_ass()`, `render_vertical(subtitle_path=None)`.
Per-job override (R-05): `jobs.watermark_width` / `watermark_opacity`
(NULL = global setting), set via `PATCH /api/jobs/{id}/render-options`.
Resolve with `job_watermark(job)` once per render and pass the same
values to `make_ass()` and `render_vertical()`. Submagic output gets the
watermark in the `applying` step (`apply_watermark_overlay()`).

## Version history

`candidate_versions` table logs a snapshot every time an edit is
actually *committed* — currently 3 trigger points, all in main.py:
`regenerate_preview` ("Applied changes"), `approve_candidate`
("Final render requested"), `submagic_use_as_final` ("Submagic render
requested"). `record_candidate_version(cur, candidate_id, label)`
must be called with the **same open cursor/transaction** as the
change it's recording, right before `conn.commit()` — it reads
current DB state, so calling it after commit or on a different
connection can race. It's a changelog, not full undo: restore
(`POST .../versions/{v}/restore`) only ever rewrites this one
candidate's own fields (subtitle text, description, thumbnail) —
it deliberately does NOT restore the snapshotted job-level
subtitle_style/font/size/animation, because those are shared across
every candidate in the job. If you add a new commit point (e.g. a
new AI-assist action that should be versioned), call
`record_candidate_version` the same way, inside its transaction.

## Submagic (optional external pass)

`SUBMAGIC_API_BASE = https://api.submagic.co/v1`. Uses the **Upload
Project** endpoint (multipart, not URL-based) because this deployment
has no public HTTPS reachability — don't switch to the `videoUrl`
variant without re-checking that assumption. No webhooks either;
`claim_submagic_poll()` polls Get Project on a 6s-per-candidate
throttle (via `updated_at`). `autoRender:false` on upload, explicit
`/export` call is the billable step — never auto-trigger it.

## AI calls (R-20)

Every AI call goes through `shared/ai/router.py`
`ai_generate_json(prompt, schema, *, task, max_tokens)` — worker
(`analyze_hooks`, task `hooks`) and main.py (`new_hook`,
`subtitle_fix`, `description`). Providers live in `shared/ai/<name>.py`
and raise only `shared/errors.py` types: `AITransientError`
(429/5xx/timeout) or `AIPermanentError` (4xx/malformed/no key). Never
import an AI SDK in main.py/worker.py. google-genai 2.x closes a
garbage-collected `Client`: keep it in a variable while calling.
Claude (`shared/ai/claude.py`) returns structured output via a strict
tool; Sonnet 5.5 / Opus 5.5 reject forced `tool_choice`, so it forces
only where the model accepts it. Claude model IDs live only in
`DEFAULT_SETTINGS` (`CLAUDE_MODEL_ANALYSIS`, `CLAUDE_MODEL_UTILITY`).
Failover (R-22): `CLIP_ANALYSIS_PROVIDER` / `TEXT_UTILITY_PROVIDER` ∈
`gemini|claude|auto` (default auto = Gemini, then Claude on transient
errors only). Circuit breaker 3 fails → 60 s, per process.
`clip_candidates.hook_provider` records who produced each hook — set
it on any new hook-producing path (pass `with_meta=True`).

## Runtime settings

One rule, one implementation: `shared/settings.py` (`RuntimeSettings`).
Precedence, first non-empty wins: **app_settings (DB) → env → caller
default / `DEFAULT_SETTINGS`**, cached 5 s per process (PUT
`/api/settings` invalidates the backend cache; the worker picks a change
up within 5 s, no restart). Worker reads via `setting()` /
`setting_int()` / `setting_float()`, main.py via `runtime_setting()`.
`DEFAULT_SETTINGS` (the PUT whitelist **and** the single source of
defaults) and `SECRET_SETTING_KEYS` live in `shared/settings.py`.
Never add an import-time `X = os.getenv("X")` constant for a setting:
read it at use time (the baseline did that and half the settings UI was
dead). Read once per job/render where values must agree (e.g.
`clip_count` in `process_analysis_job`, `size=` passed from
`create_preview` to `render_vertical`). `GET /api/settings` returns the
*effective* value plus `source` (db/env/default); the UI saves only
fields the user changed, because echoing values back would pin them in
the DB above `.env`. An empty DB value means "unset" (falls through to
env). `ENV_ONLY_KEYS` (`CLIPFLOW_API_KEY`, `CORS_ALLOWED_ORIGINS`,
`DATABASE_URL`) are never read from the DB. Still env-only by design:
`TELEGRAM_*`.

## Auth + CORS (R-03)

Every `/api/*` request needs header `X-ClipFlow-Key` = env
`CLIPFLOW_API_KEY` (env-only, never app_settings; empty = fail closed).
Enforced by the `require_api_key` **middleware** in main.py (not a route
dependency) so unknown `/api` paths get the same 401 as real ones.
`/health` and `/` are open. `<img>`/`<video>`/download URLs can't send
headers: the GET file routes matched by `MEDIA_PATH_RE` also accept
`?mt=` from `GET /api/media-token` (HMAC of the API key, stable per
12 h bucket, valid 12-24 h, read-only). **A new file-serving GET route
must be added to `MEDIA_PATH_RE`** and its frontend URL wrapped in
`mediaUrl()`; every other frontend call goes through `api()` or
`authFetch()` (uploads). Never a bare `fetch()`. CORS origins come from env
`CORS_ALLOWED_ORIGINS` (comma list, `*` dropped, no credentials). The
CORS middleware must stay added *after* the auth middleware (outermost),
or preflights get 401.

## Frontend shell (R-11/R-12/R-13, lane B 067-073; badge v2.1110)

- **Layout:** `.app-shell` grid = left `<aside id="sidebar">` (068: navigation
  only: `[data-nav]` Import/Publish switch views via `showTab()`,
  Watermarks/Settings open **sheets** `#watermarkSheet`/`#settingsSheet` via
  `openSheet()`/`closeSheet()`; `syncNav()` owns `aria-current` + the
  spring `#navIndicator`; theme toggle in `.sidebar-foot`) + `.container`.
  Sheets sit outside `#appShell`, which goes `inert` while one is open. Desktop ≥1000 px: collapsible column
  (`body.sidebar-collapsed`, localStorage). Narrow: off-canvas drawer
  (`body.sidebar-open`) over `#sidebarScrim`. Toggles are
  `[data-sidebar-toggle]`; hidden sidebar gets `inert`. **Every closed
  overlay layer must be `visibility:hidden; pointer-events:none`**:
  a stray layer once made the whole app unclickable. Import options
  (split/facecam/platform) live in `<details id="importOptions">`;
  `updateImportOptionsSummary()` runs from the `select*()` fns.
- **Toolbar (072, replaces the tabs pill):** sticky `#toolbar` with ONE title
  element `#pageTitle` ("Import"/"Publish", `syncPageTitle()`). `initToolbar()`
  is the **only** scroll driver: rAF, passive, maps `scrollY/TITLE_RANGE(48)` →
  `--p` 0..1 continuously (no threshold/hysteresis); CSS derives title
  translate/scale and `.toolbar-bg` (material + hairline + scroll-edge fade)
  opacity from `--p` — transform/opacity only. Don't add another scroll
  driver. ≤600 px: `#tabbar` bottom tab bar (same `[data-nav]`). Sidebar nav
  is the navigation; there are no `role=tab` elements any more.
- **Dynamic Island (073):** `#island` (fixed, top 8 px, centred, z 1000,
  black in both themes) is driven only by `updateJobIsland()` (same name
  as before; every caller still works). `hidden` when nothing runs. Modes
  compact (248×36, 150 on ≤600) / expanded (≤380, radius 28) via
  `setIslandMode()`; size morphs are WAAPI width/height/radius with
  spring curves from `springEasing()` (emitted as CSS `linear()`), content
  layers cross-fade (+60 ms, staggered). Events: busy → review/completed
  = ✓ auto-expand 2.5 s; → failed = red expand, then red compact until
  seen. "+N" split only in compact; it opens `#jobOverlay`. Cancel shows
  only if a global `cancelJob(jobId)` exists: it does (R-08's `window.cancelJob(id, btn)`,
  confirm + `POST /api/jobs/{id}/cancel`; the island passes its button for `setBusy`). Reduced motion: opacity
  cross-fade only. Sheets make `#appShell`, `#tabbar`, `#island` inert.
- **Busy state:** every async button/upload label goes through
  `setBusy(el, busy, label?)`. It disables the control, sets `aria-busy` and
  `.is-busy` (spinner), and restores the label. Don't hand-swap `textContent`.
- **Edit drawer:** shown via `display` + `drawerIn` keyframe. Re-renders
  while editing must add `.no-enter` (see `watchCandidate`). Description/
  Thumbnail are `<details data-edit-more>`. Their open state lives in
  `editMoreOpen["<cid>:desc|thumb"]` (capture `toggle` listener) so
  re-renders keep it. Apply/Final render sit in the sticky `.edit-actions`.
  Glass only on the drawer and that row, never over the video.
- **Status badges:** `badgeClass()` → idle (queued, `*_queued`) / running / attention (review,
  partial_failure) / completed / failed / cancelled. Colours are `--badge-*` tokens in both
  theme blocks, each pair measured ≥4.5:1 on `--panel` incl. the shimmer peak. Re-measure on change.
- **Motion & detail tokens (067):** curves `--ease-out` (.32,.72,0,1; `--ease` aliases it),
  `--ease-spring` (overshoot), `--ease-in-out`; durations `--dur-1..4` = 120/200/320/450 ms;
  press `scale(var(--press))` (.97); spacing `--sp-*` (8pt, 4pt half-step); `--hit` 44 px;
  `--font-text`/`--font-display`; materials `--material[-thin|-thick]` + `--material-blur`.
  Use tokens, not literals. Caption-preview `cpw-*` keyframes keep their own timings (they mirror ASS).
- **Reduced motion:** the CSS rule can't stop JS. Guard JS-driven motion
  with `REDUCED_MOTION.matches` / `motionMs(ms)` (animation waits → 0) (caption preview loop) and use
  `scrollMode()` for `scrollTo`/`scrollIntoView`.

## Conventions worth copying, not reinventing

- New queue → new status enum + `claim_x_task()` with `FOR UPDATE
  SKIP LOCKED` + a branch in `main()`'s loop. Don't repurpose
  `clip_candidates.status` for unrelated concerns (see why
  `submagic_status` is a separate column).
- New per-candidate DB field → `update_candidate(id, **kwargs)`
  dynamic helper, not hand-rolled SQL, unless you need a raw
  expression like `NOW()`.
- New uploaded-file endpoint → `DATA_ROOT / "<kind>/"`, store the
  path *relative to DATA_ROOT* in the DB (see thumbnail_options,
  watermark_assets.path), resolve with `DATA_ROOT / stored_path` on
  read. Never store absolute paths.
- New frontend interactive element → `data-something` attribute +
  one line in the relevant delegated `document.addEventListener`
  block near the others, not a fresh listener.

## Before touching a file, grep first

- Endpoint for X → `grep -n "@app\.\(get\|post\|put\|delete\)" main.py`
- ffmpeg/ASS rendering → `worker.py`, functions `make_ass`,
  `render_vertical`, `create_preview`, `render_final_candidate`
- Frontend button wiring → `grep -n "data-yourthing" index.html`
  (markup + handler both show up)

## Token discipline (always)
- Never read main.py / worker.py / index.html whole. `grep -n` the function, then read only ~60 lines around it.
- Logs: `docker compose logs --tail=50 <service>`, never unbounded. Build output: pipe through `tail -30`.
- Don't paste full diffs back in reports; summarise per REBUILD.md's report format.
- RTK is installed: if compressed output hides something you need, run `rtk recall <id>` instead of re-running with bigger output.
