# 090 · Progress rule: the job island is the only progress UI; GET /api/activity feeds it · main.py, index.html, CLAUDE.md, roadmap

**Rule (all phases, user decision 2026-10-02).** Every progress state (import/analysis, preview/final render,
loudnorm, Submagic, keyword AI call, brief parsing, auto-import checks, publish kit / Send to Telegram, view
pulling, auto-posting) shows in the existing Dynamic Island (own capsule, stage + %, animates independently,
only while something runs; several → count, expand to list). No new spinners, progress bars or toasts for
progress. Written into CLAUDE.md (frontend shell) and docs/roadmap.md.

**Before.** The island merged `/api/jobs?scope=current` (pipeline jobs) with tasks the browser registered
itself on click (`candidateActiveTasks`), so renders/Submagic work started elsewhere (another tab, the API,
"apply to all", retries) never showed.

**Now.**
- `GET /api/activity` → `{items:[{kind, id, job_id, candidate_id, stage, percent, label, title, updated_at}]}`:
  pipeline jobs (not resting), candidates in a busy status (queued/preview/render/thumbnail; loudnorm shows as
  the final render's 90 % "Normalising loudness" stage), Submagic steps (no % of its own: queued 0, running 50).
  New background task kinds add their rows here.
- `refreshRunningJobs()` (the always-on monitor) fetches it with the jobs list; `allActiveTasks()` merges
  candidate/Submagic items the browser isn't already tracking (click-registered tasks keep precedence: their
  label names the AI action).

**Verified** on the stack: preview re-render of 9c5f3050 started via the API (no click) → `/api/activity`
returns it (`preview_rendering`, 10 %, "Refreshing preview") and a fresh page's island shows it
("…: Refreshing preview, 10%"); idle → `{"items": []}`, island hidden.
