# 151 · P4 task 1 — Hook title card + Editor page shell (lane B)

**What:** `edit_spec.hook_title = {on, text, duration}` (text "" = clip title; 2 / 2.5 / 3 s). A white
rounded card with the hook text over the first seconds: spring pop-in + fade, shadow, ≤ 3 lines,
centred, below the watermark (never covers it) and below the 16 % top-UI band. Rendered as ASS events
in the same .ass the render burns (preview and final share the code, scaled to the canvas); captions
off → a title-only `<cid>.title.ass`. Emoji stripped (libass).

**Editor page (flow-preview step 5)**: `frontend/html/editor/` is its own view in the app shell (toolbar,
stepper, island stay), route `#editor/<job>/<clip>`, "Open editor" on each clip card. Captions tab:
Hook title card (switch, text with title placeholder + counter, Show for 2/2.5/3 s chips), auto-save
(600 ms); live CSS overlay only while changes aren't rendered; sticky footer Render preview → saves,
then the existing `regenerate-preview` (island progress via /api/activity, version history). Other
tabs are shown disabled until their tasks land. Lane A's edit drawer is untouched.

**API** `backend/app/routes_editor.py`: `GET /api/editor/candidates/{cid}`,
`PUT /api/editor/candidates/{cid}/hook-title` (400 bad value, 404 not found/not owned, 409 while
rendering; marks an existing final outdated, 114). Every route takes `get_current_user` (placeholder =
admin until P1.5) and scopes by job owner (`owner_filter`: no-op until `jobs.owner_id` exists).

**Hooks (one line each, marked lane-b hook)**: main.py `include_router`; worker.py `import render_steps`
+ `add_title_card(...)` before both `render_vertical` calls (preview + final); worker/Dockerfile COPY
(marker on the line above: Dockerfiles have no trailing comments); index.html css link, script tag,
"Open editor" link.

**Verified on staging**: API (401/400/404, PUT saves), preview render (~30 s, activity rows
preview_queued → preview_rendering), final render (~45 s, card at 1080×1920, loudness −14.2 LUFS);
preview and final frames match (in at 0.1 s, full by 0.3 s, gone by 2.7 s, under the watermark,
captions untouched). UI on :8080 at 1280/390: no errors, no overflow. Tests: `tests/test_render_steps.py`
(7), `tests/ui/specs/editor.spec.js` (3 × 2 viewports); full UI suite 42 passed on staging.

**Known for Lane A at merge:** the stepper still highlights Analyze while the editor view is open
(`renderFlow()` is Lane A's); switch the Editor step to `#editor/...` when the drawer goes.

**CLAUDE.md lines to add (Lane A):** "Editor page (P4, lane B): `frontend/html/editor/` mounted by
index.html, route `#editor/<jid>/<cid>`; API in `backend/app/routes_editor.py` (every route
`Depends(get_current_user)` + `owner_filter`); render additions in `worker/render_steps.py` called from
one-line `# lane-b hook`s. Hook title card = `edit_spec.hook_title`, burned via the caption ASS."

## Update 2026-10-06 — P1.5 merged (fixes QA a67d58c #1, merge blocker)

Routes moved under the job path: `GET /api/jobs/{jid}/candidates/{cid}/editor` and
`PUT …/editor/hook-title`, so main's ownership middleware (`JOB_PATH_RE`) guards them; `get_current_user`
now IS main's `current_user(request)`; SQL also scopes by `jobs.user_id` (owner only, admins included,
same as main). Verified on staging with real sessions: admin GET/PUT 200, a member on the admin's clip
GET/PUT **404**, no session 401, wrong job id 404. UI suite on staging: 50 passed.
