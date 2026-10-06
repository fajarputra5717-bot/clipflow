# ClipFlow — agent context (read this first, don't re-crawl the repo)

> **REBUILD COMPLETE (2026-09-30).** The original server was lost (2026-09) and
> everything in `REBUILD.md` was rebuilt except R-23/R-24 (deferred); its status
> table lists each item's commits and change docs. Keep this file current as
> invariants change.

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
`python3 scripts/check_caption_mirror.py` checks that mirror (and `CAPTION_PRESETS`) against make_ass().

Per-clip presets (108): `clip_candidates.edit_spec.caption = {style, animation}` (shared/edit_spec.py; NULL =
job style) overrides the job's style + animation for THAT clip only (font/size stay job-level), applied when the
worker builds the candidate job dict. Preset cards (`CAPTION_PRESETS`) are fixed style+animation pairs; Apply
stores the pair or clears it when it equals the job's; `POST /api/jobs/{id}/caption-preset` = "Apply to all
clips" (job style + clears every clip override + re-renders clips in review). New edit_spec keys: extend
`normalize_patch()`. Keywords (111): `edit_spec.keywords` / `keyword_color`; worker `pick_keywords()` (utility AI +
stoplists, never overwrites an existing key) runs before the first ASS; `make_ass(keywords=, keyword_color=)`
colours them in every mode (\1c+\2c, then reset to the style colours).

## Transcription (R-07)

faster-whisper (int8, CPU) via `whisper_model()` / `transcribe()` in
worker.py; model = `WHISPER_MODEL` setting (default medium; this box
has it as an app_setting because `.env` pins base). Models live in the
`hf_cache` volume (`HF_HOME=/cache/huggingface`). `transcribe()` must
keep returning per-word `{word,start,end}`: karaoke depends on it.
Every analysis stage is timed (`StageTimer`, one summary log line).
Language (079): `jobs.language` auto|en|id (NULL = legacy = id); read the resolved one with
`shared.languages.job_language(effective_language, language)` everywhere (prompts, Submagic). Auto detects
in `transcribe(language="auto", fallback=…)`; < 0.6 or not en/id → the form's last explicit choice.
Indonesian hook-prompt wording is frozen (eval baseline); new language-specific text goes in a branch.
Caption text (083): `subtitle_text` = the transcript lines, `subtitle_override` = ONLY real user edits
(NULL/"" = none; never seed or write it back). `apply_subtitle_override()` aligns edited words to Whisper's
(difflib): unchanged lines keep their segment + words, edited ones get timings from the words they
replaced; never an even split. `subtitle_segments` = exactly what make_ass() burned.

## Caption fonts (R-19)

`shared/fonts.py` `CAPTION_FONTS` is the whitelist (backend normaliser
+ worker `make_ass()`); index.html mirrors it by hand. Display fonts
select weight by name ("Montserrat Black") with ASS Bold=0 — never add
`\b`/Bold on top (libass faux bold). Unknown font → default + log line.
Captions strip emoji (libass can't draw them). Files: `worker/fonts/`,
also served to the browser at `/fonts/` (nginx alias).

## Campaigns (081)

`docs/campaigns/<slug>.rules.json` (+ `.md` brief) mounted at `/app/campaigns`, read via `shared/campaigns.py`
(mtime cache). `jobs.campaign` = slug (NULL = none). Campaign watermark preset is snapshotted on the job
(`watermark_asset_id` + R-05 width/opacity + position) — resolve with `resolve_watermark_path(job["watermark_asset_id"])`.
Hashtags (093): `hashtags.required_in_order`, exact ORDER, appended at the END of the caption (position is
not a rule). Campaign-only prompt additions; the non-campaign hook prompt must stay byte-identical. Clip-checkable
content rules → `rule_flags` → `drop_rule_breakers()`; posting rules (`POSTING_RULES`) are not clip checks.
Rule chips (109): `shared/rule_checks.check(rules, candidate)` is the ONE source for the UI chips (`rule_checks`
in `GET /api/jobs/{id}`) and the approve gate (409). Blocking: length per platform (`PLATFORM_LIMITS`, from Lane B's
research doc), hashtags, watermark. Warning only: content safety (`clip_candidates.safety_check`, worker
`content_safety_check()`, utility model). New rule → add it there, not in the frontend.

## Facecam layout hint

`jobs.layout` ∈ `auto|left|right|none`, set once at job creation (Import
form choice-grid; `none` / no face detected → `face_crop.panel=false` → full-frame 9:16 gameplay,
no bottom panel, via `vertical_layout_filter()`, the ONLY layout graph — 087),
layout is decided PER JOB (095: `decide_face_layout()` → `jobs.face_layout`, majority, or a tie whose hit is
`facecam_like()` (corner/edge + ≥ 3 hits, spread ≤ 0.03 + persistence ≥ 0.5 of sampled frames; 101/118); only
facecam-like hits count, panel if they're ≥ half the clips, else full for all; with layout auto a non-facecam
detection is dropped per clip; pass `face_layout=job.get("face_layout")` to every `detect_face_for_clip`), read by `detect_face_for_clip(..., layout=...)` in
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
the job owner's `ACTIVE_WATERMARK_ID` user setting (P1.5), resolved fresh per render by
`resolve_watermark_path()` in worker.py — never read `WATERMARK_PATH`
directly in new code, call the resolver.
Per render use `job_watermark_path(job, candidate_id)` (092): a job's own (campaign) asset that can't be
resolved → `False` = NO watermark + failing `campaign_watermark` chip + WARNING log; never a silent fallback.

Geometry (R-16): `get_watermark_rect()` is the only placement logic
(alpha-bbox crop; `WATERMARK_WIDTH` = visible mark width at 1080).
`make_ass()` returns the rect after clearing the caption top edge (the
watermark moves up; captions never go below the seam) and the render
must use that same rect via `render_vertical(watermark_rect=…)`.
Floor (078): never above `WATERMARK_MIN_Y_FRAC` (16 %, platform top UI); the caption push-up
stops there and logs a WARNING instead of going higher.
Positions (R-17): `jobs.watermark_position_y` / `subtitle_seam_gap` are
snapshotted from settings at job creation; `job_layout(job)` → NULL =
legacy 50 % / 4 %. Pass its values to make_ass/get_watermark_rect.
Burn-in toggle (R-09): `jobs.burn_subtitles` (NULL = on, `job_burn_subtitles()`); off = no `make_ass()`, `render_vertical(subtitle_path=None)`.
Per-job override (R-05): `jobs.watermark_width` / `watermark_opacity`
(NULL = global setting), set via `PATCH /api/jobs/{id}/render-options`.
Resolve with `job_watermark(job)` once per render and pass the same
values to `make_ass()` and `render_vertical()`. Submagic output gets the
watermark in the `applying` step (`apply_watermark_overlay()`).

## Loudness + retention engine (085/086)

`shared/retention.py` (Lane B) = pure ffmpeg argv/filter builders: silence trim + `TimeMap` word re-timing,
two-pass loudnorm, punch-in zoom. Wired so far: ONLY loudnorm, via `normalize_loudness()` on native finals, Submagic finals and previews
(091: never fatal; a failure keeps the file and sets a `render_warnings` "loudness" chip). Finals: (−14 LUFS, limiter −1 dBTP minus codec headroom, video stream-copied, verified with
ebur128 and logged). It is the LAST audio step: any future SFX/music mix goes before it. Silence trim and
zoom stay unwired (opt-in later via the Audio/Effects tabs). Cuts change the timeline: re-time
words/markers with `retention.TimeMap` built from the same keep segments.

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
every candidate in the job. It DOES restore the clip's own `edit_spec` (108; pre-108
snapshots without the key keep the current spec). If you add a new commit point (e.g. a
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
Hook input (077): `select_hooks()` sends the WHOLE timed transcript (no cut) up to
`HOOKS_FULL_TRANSCRIPT_MAX_CHARS`; above it, 30-min windows (+2 min overlap) → `dedupe_hooks()` → one
ranking call returning candidate ids. Providers return `(data, model, usage)`; router `meta["usage"]`.
Keep prompt construction in `build_hooks_prompt()` so the eval and production send identical text.

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
env). Per-user (P1.5, 123): `USER_SETTING_KEYS` resolve **user_settings → app_settings → env → default** for a
user (`runtime_setting(key, user_id=…)` in main.py; the worker's `setting()` uses the job owner set by
`run_as_owner()` in `main()`'s loop: every new claimed-task branch must go through it). `USER_ONLY_KEYS`
(ACTIVE_WATERMARK_ID) have no global fallback. Members see/PUT only user keys; global keys are admin-only (403).
`ENV_ONLY_KEYS` (`CLIPFLOW_ADMIN_USER/PASSWORD`, `CORS_ALLOWED_ORIGINS`,
`DATABASE_URL`) are never read from the DB. Still env-only by design:
`TELEGRAM_*`.

## Auth + CORS (P1.5, was R-03)

Every `/api/*` request needs a principal; the `require_user` **middleware** in main.py (not a route dependency, so
unknown `/api` paths also 401) puts `{id, username, role, via}` on `request.state.user`; read it with
`current_user(request)` / `require_admin(request)`. Sources (`app/auth.py`): session cookie `clipflow_session`
(HttpOnly, SameSite=Lax; DB row in `user_sessions`, token stored as sha256; disabled user = dead session) →
per-user API token `cf_…` (`X-ClipFlow-Key` or `Authorization: Bearer`; `api_tokens` stores sha256 only;
managed in the Account sheet from a session only, never by a token; 124) → (the shared `CLIPFLOW_API_KEY` admin
key was removed in 127; there is no shared key) →
`?mt=` per-user media token (`exp.user_id.sig`, GET/HEAD on `MEDIA_PATH_RE` only). Open: `/api/auth/login|logout`,
`/health`, `/`. Passwords argon2id; login 429 after 5 fails/user or 20/IP per 15 min; no signup route.
First run: `CLIPFLOW_ADMIN_USER/PASSWORD` (env-only, read only while `users` is empty). Cookie-authed writes
with a foreign `Origin` → 403. **A new file-serving GET route must be added to `MEDIA_PATH_RE`** and its
frontend URL wrapped in `mediaUrl()`; every other frontend call goes through `api()` or `authFetch()` (uploads),
never a bare `fetch()` (exception: the login form + `ensureSession()`/`signOut()`). A 401 opens `#loginScreen`
(`showLogin()`, `body.auth-locked`) and retries once. Account sheet (`#accountSheet`, username in the sidebar foot): change password (≥ 12) + Sign out. Users (125): admins only
(`/api/admin/*`, middleware 403 for members; Settings → Users); create/reset set `must_change_password` (session limited to
`/api/auth/me|password` until changed; `#forceForm` in the login layer); disable deletes sessions + API tokens; never
leave zero active admins (409, rows locked). CORS origins from env `CORS_ALLOWED_ORIGINS` (comma list,
`*` dropped, no credentials); the CORS middleware stays added *after* the auth middleware, or preflights get 401.

## Ownership (P1.5) — every query is scoped by `user_id`

Owned tables carry `user_id` NOT NULL (`jobs`, `watermark_assets`, `platform_accounts` (128), `clip_posts` (129), `clip_post_views` (133); candidates/versions via
their job; **every new table from now on**). Rule: every SQL that reads or writes user data filters by the caller's id
(`current_user(request)["id"]`); another user's row answers **404**, never 403/200. The middleware guard
`_path_owned()` already enforces it for `/api/jobs/{id}[/candidates/{cid}]…`, `/api/assets/watermarks/{id}…` and
`/api/accounts/{id}…`, `/api/posts/{id}…`;
lists and inserts do it in the handler. A new route family keyed by an owned id → add its regex to the guard.
Admin is scoped like everyone except `/api/activity` (sees all, `owner` set). Campaigns are a shared catalogue
(admin edits; P3 adds `created_by` + `visibility`); `source_videos` is a shared download cache.
Writing tests (cross-user, settings, qa-tmp users) run on staging only (:8080/:8001), never production.

## Posts (P2, 129)

`clip_posts` = one row per clip per platform post; every writer (manual UI now, auto-poster/view tracker later)
validates through `shared/posts.py` (status lifecycle, required fields, URL host per platform, paid_rp whole IDR).
Posted rows are history: never deleted (drop them); an account with posts is paused, never deleted. Publish step (130):
`GET /api/publish-queue` builds rows server-side (clip × campaign platform; caption via `campaigns.caption_body` +
hashtags in order, trimmed by `posts.trim_caption`, never cutting tags); downloads use `…/render?download=<platform>`
(server-side filename). Copy buttons go through `copyText()` (sync Clipboard API in the tap + execCommand fallback). Pre-post
checks (132): red = `rule_checks` blocking failures (same as Approve; posting → 409); amber = `payouts.window_problems`
/ `cap_problem` / platform length; posting with warnings stores `eligible=false` + `ineligible_reason` (computed
server-side). Windows, caps and payout math live ONLY in `shared/payouts.py` (Lane B module, 131). Claims (133):
advice = `payouts.claim_advice` per post (views history `clip_post_views` gives the 24 h growth); claimed stores
`claimed_views` + `expected_rp`; amounts reach the UI pre-formatted (`*_fmt`), never computed in index.html. Payout amounts
come only from Lane B's `shared/payouts.py` (P3), never hand-rolled.

## Frontend shell (R-11/R-12/R-13, lane B 067-073; badge v2.1117)

- **Navigation (106, P1 task 0):** the flow-preview **stepper** (`#flowNav`, `renderFlow()`, `FLOW_STEPS`) is the
  top-level navigation (sticky under the toolbar, compact while it is collapsed via `body:has(.toolbar.is-collapsed)`, 121): Analyze (`data-nav="current"`, the Import view), Review (`data-nav="queue"`, the job
  list/detail, formerly "Publish"), Publish (`data-nav="publish"`, 130), Editor (`data-flow-editor`: opens the visible job's clip drawer; disabled
  until a job detail is open); Campaign/Auto-import/Track (P3) and Schedule/Publish (P2) are disabled with
  "Coming in Px" — never mock content (mapping: docs/roadmap.md). `#pageTitle` = the active step. Gear in the
  toolbar (`data-nav="settings"`). `syncNav()` repaints the stepper.
- **Layout:** `.app-shell` grid = left `<aside id="sidebar">` (tools only since 106:
  Watermarks/Settings open **sheets** `#watermarkSheet`/`#settingsSheet` via
  `openSheet()`/`closeSheet()`; `syncNav()` owns `aria-current` + the
  spring `#navIndicator`; theme toggle in `.sidebar-foot`) + `.container`.
  Sheets sit outside `#appShell`, which goes `inert` while one is open. Desktop ≥1000 px: collapsible column
  (`body.sidebar-collapsed`, localStorage). Narrow: off-canvas drawer
  (`body.sidebar-open`) over `#sidebarScrim`. Toggles are
  `[data-sidebar-toggle]`; hidden sidebar gets `inert`. **Every closed
  overlay layer must be `visibility:hidden; pointer-events:none`**:
  a stray layer once made the whole app unclickable. Analyze step (126) = flow-preview
  step 3: segmented `<button aria-pressed>` controls + layout cards (`data-layout-card` facecam|full → `jobs.layout`
  auto/left/right | none; 3 disabled "Coming soon" cards, P4); campaign `default_layout`/`default_language` pre-fill
  with a "from campaign" tag unless touched; estimate from `GET /api/analysis-estimate` (own jobs; hidden without
  history). POST /api/jobs payload unchanged (analyze.spec pins it).
- **Toolbar (072, replaces the tabs pill):** sticky `#toolbar` with ONE title
  element `#pageTitle` ("Analyze"/"Review"/"Editor", `syncPageTitle()`). `initToolbar()`
  is the **only** scroll driver: rAF, passive, maps `scrollY/TITLE_RANGE(48)` →
  `--p` 0..1 continuously (no threshold/hysteresis); CSS derives title
  translate/scale and `.toolbar-bg` (material + hairline + scroll-edge fade)
  opacity from `--p` — transform/opacity only. Don't add another scroll
  driver. ≤600 px: `#tabbar` bottom tab bar (Analyze / Review / Watermarks / Settings, same `[data-nav]`); the
  stepper scrolls horizontally.
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
- **Progress = the island, only (090, all phases).** Every progress state on the platform (import/analysis,
  preview/final render, loudnorm, Submagic, keyword AI call, brief parsing, auto-import checks, publish kit /
  Send to Telegram, view pulling, auto-posting) shows in the Dynamic Island: its own capsule, stage + %,
  animates independently, only while something runs; several at once → count + expand/list. **No new
  spinners, progress bars or toasts for progress** (`setBusy()` on the clicked control stays). Backend side:
  `GET /api/activity` → `{items:[{kind, id, job_id, candidate_id, stage, percent, label, title}]}` is the
  one feed; a new background task kind adds its rows there (and keeps `status/progress/message` on its row),
  never a new progress UI. The island merges it in `allActiveTasks()` (polled by `refreshRunningJobs()`). Jobs appear only for statuses in
  `JOB_RUNNING` (allow-list); `percent: null` = indeterminate (spinning ring, no %); feed errors keep the last
  state and back off (102).
- **Card-level progress (P0):** Import job-card bars and Publish queue row progress become small island-style
  capsules (same shape/colours/motion); the island stays the only global progress indicator.
  Implementation: `miniIslandHtml()` / `patchMiniIsland(el, p, status, label)` (`.mini-island`: black capsule,
  ring + stage + %, ring glides like the island's; only `.is-running` animates). Don't add bars back.
- **Job cards (074):** `#currentJobs` is keyed by job id: `syncCurrentJobs()` patches via
  `patchJobCard()` (`setText`/`setAttr`, bar `transform`), new → `createJobCard()`, gone →
  `leaveJobCard()`. Never re-render polled lists with innerHTML (flicker); same for the island
  and `#jobOverlayList`. Card status line = `jobStatusLine(j)`, not `isBusy()` (BUSY lacks `processing`).
  Motion (075): only `.job-card.is-running` animates (mini-island ring glide + dot breathe); queued/idle cards and
  the island's idle lead are static. Don't add card-level shimmer/glow back.
- **Busy state:** every async button/upload label goes through
  `setBusy(el, busy, label?)`. It disables the control, sets `aria-busy` and
  `.is-busy` (spinner), and restores the label. Don't hand-swap `textContent`.
- **Edit drawer:** tabs (082) Captions/Effects/Audio/Watermark/Export, active tab in `editTab[cid]`;
  inactive panels stay in the DOM (`hidden`) because `applyEdits()` reads their inputs. Shown via `display` + `drawerIn` keyframe. Re-renders
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
  Use tokens, not literals. Visual system (107) = flow-preview's: the last CSS block in index.html sets the base type scale
  (15 px body, 24/17 headings), buttons (secondary = `--fill`), panels (24 px, `--shadow`) and inputs; new UI
  follows the mockup's components. Caption-preview `cpw-*` keyframes keep their own timings (they mirror ASS).
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

## UI tests (104)

`tests/ui/run.sh` (Playwright, mocked `/api` from `tests/ui/fixtures.js`, never creates jobs; desktop 1280 +
mobile 390). Run it before committing frontend changes; add a spec for new UI. Live read-only mode:
`CLIPFLOW_UI_LIVE=1 CLIPFLOW_API_TOKEN=cf_… tests/ui/run.sh specs/live.spec.js`.

## Token discipline (always)
- Never read main.py / worker.py / index.html whole. `grep -n` the function, then read only ~60 lines around it.
- Logs: `docker compose logs --tail=50 <service>`, never unbounded. Build output: pipe through `tail -30`.
- Don't paste full diffs back in reports; summarise per REBUILD.md's report format.
- RTK is installed: if compressed output hides something you need, run `rtk recall <id>` instead of re-running with bigger output.
