# QA review · a67d58c (lane-b) · P4 task 1: hook title card + Editor page shell + editor API
Reviewer: Lane C · 2026-10-06 · staging (lane-b code)

Staging checks: Playwright (lane-b suite incl. new editor.spec, against :8080) **42 passed, 4 skipped, 0 failed**.
Render: staging clip 6ec88845, `PUT /api/editor/candidates/{cid}/hook-title {on, text:"", duration:2.5}` → 200;
bad duration 9 → 400; regenerate-preview → card with the clip title at 0.6 s and 2.0 s, gone at 3.5 s; below the
watermark, captions + karaoke intact (`frames/lane-b-a67d58c/strip.jpg`, 3 frames).

## Findings (most severe first)
1. **HIGH (merge blocker) · editor API has no real ownership check once merged with P1.5.**
   `backend/app/routes_editor.py:39` `get_current_user()` is a placeholder (everyone = admin) and `:56`
   `owner_filter()` looks for `jobs.owner_id`, but main's P1.5 column is **`jobs.user_id`**, so it returns `"TRUE"`
   forever. `/api/editor/candidates/{cid}` is also outside main's ownership middleware (`JOB_PATH_RE` covers only
   `/api/jobs/{id}/…`). Result after merge: any member can read and change any user's clip via the editor API.
   Fix before merge: use main's principal (`current_user(request)`), scope by `j.user_id`, and add
   `^/api/editor/candidates/([^/]+)` to the middleware guard (or move the routes under `/api/jobs/{job}/candidates/{cid}`).
   Then QA runs `qa-multiuser.spec.js` (+ an editor case) on staging.
2. Low · staging clip 6ec88845 left with hook title on (staging data only).

**Merge: NOT OK** (#1).
