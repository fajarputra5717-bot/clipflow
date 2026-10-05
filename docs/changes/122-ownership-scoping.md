# 122 · P1.5 part 2: ownership (user_id) + scoping; other users' rows are 404 · main.py, docs/tasks/P1.5-multiuser.md

- **Columns:** `jobs.user_id`, `watermark_assets.user_id` (FK users, indexed). Candidates are owned via their job.
  Startup `assign_legacy_rows()` gives every NULL row to the bootstrap admin, then `SET NOT NULL` (`OWNED_TABLES`).
- **Central guard:** the auth middleware 404s any `/api/jobs/{job_id}[/candidates/{cid}]…` path unless the job is
  the caller's (and the candidate belongs to that job), and any `/api/assets/watermarks/{id}…` path unless the
  asset is the caller's (`_path_owned`, `JOB_PATH_RE` / `WATERMARK_PATH_RE`). Covers every current and future
  handler under those prefixes, file routes included (session cookie or per-user `mt`).
- **Lists/inserts:** `GET /api/jobs` + `GET /api/assets/watermarks` filter by `user_id`; `POST /api/jobs` and
  watermark upload set it. `GET /api/activity`: own rows; admin sees all, other users' rows carry `owner`.
- **Campaigns stay shared** (owner decision, noted in the task doc): readable/usable by all, admin edits; a campaign
  watermark resolves only to an admin-owned asset. P3 adds `created_by` + `visibility`.
- source_videos stays a shared download cache (keyed by URL; public YouTube metadata).
- Known gap → part 3: `ACTIVE_WATERMARK_ID` and every setting are still global (a member could PUT them).

**Verified (prod, before the staging-only rule):** backfill 21/21 jobs + 2/2 watermarks to admin, NOT NULL; Lane C
`qa-multiuser.spec.js` 8/9 (B: 404 on A's job/candidates/versions/files with and without B's mt, lists + activity
clean, writes refused with A's data unchanged, anon 401); the 9th (member PUT global setting) fails until part 3 —
it wrote WHISPER_MODEL=tiny on prod; restored to medium, the two jobs analysed with tiny were re-imported.
