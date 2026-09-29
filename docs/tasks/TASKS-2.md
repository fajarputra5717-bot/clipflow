# ClipFlow — phase 2 work order

Phase 1 (TASKS.md, tasks 1–7) is merged. This is the next phase,
written from five angles: Apple HIG/UX, backend engineering, video
editing craft, and audience growth.

**Before starting:** phase 1 changed the render path, the analysis
pipeline, and the edit panel. Read `CLAUDE.md` and
`docs/changes/INDEX.md` first, then open only the `docs/changes/`
entries for the areas a task touches. Function names below are
stable; **don't trust any line numbers you remember — grep.**

Same ground rules as TASKS.md apply verbatim: one task = one commit,
a `docs/changes/NNN-<slug>.md` entry + INDEX line per task, schema via
`ensure_schema()`'s `statements` list, settings via
`DEFAULT_SETTINGS`, compile checks before each commit, and honest
"what I did NOT verify" notes.

Tasks are ordered by risk, not by appeal. **Do P0 first** — it
prevents data loss and outages. P1 is where audience actually comes
from. P2 is scale/product.

---

# P0 — things that will bite you

## Task 1 — Disk retention policy

`DATA_ROOT` currently grows forever. Files are only ever deleted when
a user explicitly deletes a job (`delete_job` in `main.py`). Every
job leaves behind: the source download, the normalized copy, extracted
audio, a preview render, a clean plate (task 3 of phase 1), a final
render, and N thumbnails. On a local server this fills the disk, and
the failure mode is ugly — ffmpeg dies mid-render with a confusing
error, mid-pipeline, on an unrelated job.

- Add a retention sweep to the worker loop (low priority, runs when
  idle): delete intermediate artifacts (`DOWNLOAD_DIR`, `AUDIO_DIR`,
  `NORMALIZED_DIR`, clean plates) for jobs whose candidates are all
  `completed`/`cancelled`/`failed` and older than
  `RETENTION_DAYS_INTERMEDIATE` (default 3). **Never** auto-delete
  final renders or thumbnails — those are the user's output.
- Add an orphan sweep: files on disk with no DB row pointing at them
  (from failed jobs, crashed renders, deleted rows). Log what it would
  delete on the first pass; only delete on a second confirmed run or
  behind a setting defaulting to dry-run.
- Surface free disk space in the UI settings panel and **refuse to
  start a new analysis job below a threshold** with a clear message,
  rather than failing deep in the pipeline.

## Task 2 — Auth + CORS

`allow_origins=["*"]` with no authentication on any endpoint. Fine on
localhost; a serious hole the moment this is port-forwarded, reachable
over a LAN, or tunneled. Endpoints can delete jobs, spend Gemini
credits, and trigger billable Submagic renders.

- Add a single shared-secret header check (e.g. `X-ClipFlow-Key`)
  applied via FastAPI dependency to all `/api/*` routes except a
  health endpoint. Store the expected value in env, not the DB (the
  DB settings table is served over the API — don't make the key
  readable through the thing it protects).
- Lock `allow_origins` to the actual frontend origin(s), configurable.
- Frontend sends the header on every `api()` call and the raw
  `fetch()` upload calls. Prompt for the key once, keep in
  `sessionStorage`.
- Rate-limit the AI endpoints (Gemini hook/typo/thumbnail, Submagic
  export) — a stuck frontend retry loop currently spends real money.

## Task 3 — Job failure recovery

A worker crash mid-render leaves jobs stuck in `rendering` /
`analyzing` forever with no way back except manual SQL.

- Add a heartbeat: worker writes `updated_at` periodically during long
  stages. On startup and periodically, reclaim rows stuck in a
  non-terminal state with no heartbeat for N minutes — reset to
  `queued` (with an attempt counter) or mark `failed` after
  `MAX_ATTEMPTS`.
- Add a "Retry" button for `failed` jobs and candidates. Right now the
  only recovery is delete-and-redo, which loses all edits and version
  history.
- Distinguish transient failures (network, 429, ffmpeg OOM) from
  permanent ones (bad URL, unsupported codec) in `error_stage` /
  `error_message`, and only auto-retry the transient class with
  backoff.

---

# P1 — this is where audience comes from

## Task 4 — Performance feedback loop

**The single highest-leverage thing in this document.** Right now the
app makes clips and forgets them. Hook selection, thumbnail choice,
caption style, clip length — all of it is guesswork, permanently,
because nothing ever measures what worked.

- Pull YouTube Analytics for published clips (views, avg % viewed,
  retention curve if available, CTR, likes/comments) on a schedule.
  The YouTube upload path already exists, so the video ID is known.
- Store a `clip_performance` table keyed by candidate. Show it in the
  UI as a simple leaderboard: which clips won, sorted by retention and
  CTR, not raw views.
- Feed it back into the Gemini hook prompt: include the user's own
  top-performing hooks as few-shot examples. This is the difference
  between a generic clipper and one that learns a specific channel's
  audience.
- Correlate what's actually controllable: caption style, animation,
  clip duration, hook category (the existing Funny/Wise/Reality/Hype/
  Wholesome taxonomy), thumbnail choice. Report honestly when the
  sample is too small to conclude anything — don't render a chart off
  four clips and imply it's signal.

## Task 5 — Retention editing (the actual craft gap)

Shorts live or die in the first 1–2 seconds and on dead-air pacing.
The pipeline currently takes a contiguous slice and renders it flat.

- **Silence/dead-air trimming:** detect pauses > ~400ms in the
  transcript's word timings (already available) and tighten them.
  Biggest single retention win available, and the data's already there.
- **Hook-first ordering:** if the strongest line lands 6 seconds in,
  the clip is dead. Either bias `analyze_hooks` toward clips whose
  hook is in the first 2 seconds, or support a cold-open (the hook
  line first, then cut back). Flag which approach you chose.
- **Audio loudness normalization:** there's no `loudnorm` anywhere in
  the ffmpeg chain. Shorts audio should sit around -14 LUFS; quiet
  clips get scrolled past. Add a `loudnorm` filter pass — cheap,
  immediate, uncontroversial.
- **Punch-in on emphasis:** slight scale-up on the gameplay pane during
  loud/emphasized moments. This is Submagic's signature move and a
  large part of why their output feels energetic.

## Task 6 — Caption safe zones per platform

Captions are positioned generically, but every platform overlays its
own UI: TikTok's right action rail and bottom caption/handle area,
Reels' bottom bar, Shorts' title + progress bar. Captions rendered
into those regions get covered.

- Define per-platform safe-area insets and apply them to the ASS
  margins in `make_ass()`. `platform` is already stored on the job.
- Show the safe zone as an overlay in the preview panel so the user
  can see what will be covered.
- Verify against current (2026) platform layouts rather than
  hardcoding numbers from memory — these change.

## Task 7 — Hook prompt quality

The Gemini hook selection is the product's core differentiator and
it's a single prompt that's never been evaluated.

- Build a small eval set: 10–20 clips with known outcomes (once task 4
  has data). Test prompt variants against it rather than tweaking by
  vibes.
- Add explicit criteria to the prompt: curiosity gap, emotional peak,
  self-contained context (does this make sense to someone who hasn't
  watched the source?), and a strong opening line.
- Have it return a *reason* per candidate, shown in the UI. The user
  learns what the model is optimizing for and can correct it.
- Generate 2–3 title variants per clip for A/B testing, not one.

---

# P2 — scale & product

## Task 8 — Replace polling with server-sent events

The frontend polls `/api/jobs/<id>` every 2–2.5s per watched
candidate, re-fetching the full job payload each time. It's wasteful
and makes the UI feel laggy at exactly the wrong moments.

- Add an SSE endpoint streaming job/candidate status changes.
- Keep polling as a fallback when SSE fails.
- This should visibly improve perceived responsiveness — progress
  updates arrive on change instead of up to 2.5s late.

## Task 9 — Batch operations

Everything is one-clip-at-a-time. Real channel operation is batch.

- Multi-select candidates → render all / approve all / export all.
- Queue multiple source URLs at once.
- A publish schedule: pick a cadence and let the app drip clips out,
  rather than manually uploading each. Posting consistency matters
  more for growth than any individual clip's polish.

## Task 10 — UX: the edit panel is now very dense

Phase 1 added watermark size, burn-in toggle, animation, version
history, and Submagic to a panel that already held subtitle text,
style, font, size, description, thumbnails, and actions.

- Split into tabs or a sectioned accordion with clear grouping:
  **Content** (text, title, description) / **Style** (font, animation,
  size, watermark) / **Output** (burn-in, thumbnail, render, Submagic).
- Keep "Apply changes" persistently visible — it's the primary action
  and must never scroll out of reach.
- Add keyboard shortcuts for the main loop (next/prev candidate,
  apply, approve) — this app is used repetitively, and repetitive use
  is exactly what shortcuts are for.
- Add an undo affordance for destructive actions (delete, cancel,
  restore version). Version history exists; surface it as undo.
- Empty and error states: most failure paths currently `alert()`.
  Replace with inline, recoverable messaging that says what to do next.

---

## What I'd do first if you only do three things

1. **Task 1 (disk retention)** — this will break the app unprompted.
2. **Task 4 (performance feedback)** — without it, every other
   creative decision stays guesswork forever.
3. **Task 5 (silence trimming + loudness)** — the cheapest real
   improvement to what the audience actually sees and hears.
