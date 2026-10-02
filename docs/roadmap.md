# ClipFlow roadmap (decided 2026-10-02)

Target: the full platform from `frontend/html/flow-preview.html`:
Campaign → Auto-import → Analyze → Review → Editor → Schedule → Publish → Track.

**Gate.** A phase starts only after Lane C (QA) signs off the previous one, in `docs/qa/`. Any open **High**
bug blocks the next phase. Each phase ships as one commit per item, with a `docs/changes/` entry, verified on
the running stack.

**Progress UI (all phases).** Every progress state uses the existing Dynamic Island (R-13 style: own capsule,
stage + %, animates independently, only while something runs; several at once → count, expand to list): import
and analysis, renders, loudnorm, Submagic, keyword AI, brief parsing, auto-import checks, publish kit /
Telegram, view pulling, auto-posting. No new spinners, progress bars or toasts for progress. Backend tasks
expose `stage`, `percent`, `label` through `GET /api/activity` (090).

**Money.** Amounts are IDR first (Rp, `.` thousands). Every payout or claim amount comes from Lane B's
`shared/payouts.py`; nothing hand-rolls payout math in main.py, worker.py or index.html.
Rules files are the input (e.g. Fandra Octo: Rp 12.000 per FULL 3.000-view block, floor, up to 500.000
views → max Rp 1.992.000).

**UI spec (decided 2026-10-02).** `frontend/html/flow-preview.html` is the UI/UX spec for the WHOLE app, not
only the editor. P1 task 0 ("UI shell") ships the 8-step stepper as top-level navigation and the mockup's visual
system (colours, cards, spacing, type, light/dark toggle) app-wide; the job status island stays exactly as it is
(CLAUDE.md rule) and Settings stays reachable (sidebar + gear). Steps not built yet are visible but disabled:
"Coming in P2" / "Coming in P3", never mock content. Each later phase builds its step screen to match the mockup.
Money: IDR everywhere; payout wording comes from Lane B's `shared/payouts.py` models (fixed-at-threshold,
per-block with cap); "$ CPM + cap" only for a campaign that really is CPM. (No screen shows money until P2.)

| # | Mock screen (flow-preview) | Real screen today → after task 0 | Endpoints | Built in |
|---|---|---|---|---|
| 1 | Campaign: campaign cards (rate, cap, due, posted, budget meter), "New campaign" brief → rules | none (campaigns are rules files; Import has a dropdown) → step disabled "Coming in P3" | `GET /api/campaigns` (+ P3: brief_parser, save rules) | P3 |
| 2 | Auto-import: source channels with watch switches, recent imports | none → disabled "Coming in P3" | P3: Lane B `source_watch` | P3 |
| 3 | Analyze: URL, campaign, language, layout, start analysis, stage list | **Import** view (URL + preview, campaign, options: split / facecam / platform / language) + running job cards (mini-island capsules) | `POST /api/jobs`, `GET /api/jobs?scope=current`, `GET /api/activity` | exists → restyled in task 0 |
| 4 | Review: clip cards sorted by hook score, rule chips, approve | today's **"Publish"** view (job list → job detail with candidate previews) → renamed **Review** | `GET /api/jobs?scope=queue`, `GET /api/jobs/{id}`, `POST …/approve` | exists → restyled in task 0; score chip + rule chips + approve gate in P1 |
| 5 | Editor: player, Captions / Effects / Audio / Watermark / Export tabs, timeline | candidate **edit drawer** (tabs, 082) → the Editor step opens the selected clip's editor; disabled until a clip is picked | `PATCH …/candidates/{cid}`, `POST …/regenerate-preview`, `PATCH …/subtitle-style`, `PATCH …/render-options`, versions | P1 (presets, chips, score, keywords); P4 (timeline, effects) |
| 6 | Schedule: prime-time slots in the viewer's TZ, platforms per clip | none → disabled "Coming in P2" | P2: `clip_posts` (planned) | P2 |
| 7 | Publish: per-platform queue with status + retry | none (today's "Publish" = review list, renamed) → disabled "Coming in P2" | P2: v2a Ready to post, accounts, `clip_posts`, Telegram | P2 (manual), P5 (auto-post) |
| 8 | Track: views → earnings per post | none → disabled "Coming in P3" | P3: `clip_posts.views`, `shared/payouts.py` | P3 (P5 pulls views) |
| – | Settings / Watermarks | sheets from the sidebar → kept; plus a gear in the toolbar | `GET/PUT /api/settings`, `/api/assets/watermarks` | exists |

| Phase | Scope | Depends on |
|---|---|---|
| **P0** Stabilise (current queue) · **built 2026-10-02 (083–098), awaiting Lane C sign-off** | Loudness: Submagic "use as final" path, failure → keep the final + UI warning, ~2× disk reserve, single-pass on previews · unresolvable campaign watermark → failing chip + log, no silent fallback · hashtags at the END, exact order (rules wording "order", not "prefix") · min analysis window 10 min · layout auto decided per job (majority of clips with a face → camera layout for all, logged) · full-frame captions lower (~75–80 %, configurable, above platform UI) · job-card / Publish-row progress as small island-style capsules · cleanup: watermark height min 16 %, `WHISPER_LANGUAGE` labelled "Fallback language", version badge bump | n/a |
| **P1** UI shell (task 0) + editor redesign | Per-clip caption presets (`edit_spec`) + "Apply to all clips in this job" · rule chips + "Fix N rules to approve" gate (platform limits from Lane B's `docs/research/publishing-apis.md`, e.g. FB Reels 3–90 s) · existing score shown as "AI estimate" · AI keyword highlight (utility model, stoplists, click to toggle, baked into ASS). Backlog (Low): light compression before loudnorm for peaky sources (they land ≈ −15.2 LUFS after the corrective pass). Tabs already shipped (082). | P0 |
| **P2** Manual publish (v2a) | accounts · `clip_posts` · Ready to post · pre-post checks · claim advice · Telegram send + 09:00 WIB digest (6 parts, as agreed) | P1 |
| **P3** Campaigns + intake + Track | Campaign screen: brief → rules via Lane B's `brief_parser`, Lane A confirms before saving · auto-import via Lane B's `source_watch` · Track dashboard (views, claims, Rp from `shared/payouts.py`) | P2 |
| **P4** Timeline + effects | Trim timeline + click-to-seek, silence/filler removal (opt-in, Audio tab), zoom punch-ins, hook title, progress bar, transitions + CC0 SFX, using Lane B's `shared/retention.py` | P3 |
| **P5** Auto-post + view pulling | IG/FB Reels auto-post and view pulling into `clip_posts` (official APIs per the research doc) | P4 |

Lane B modules not on main yet: `shared/payouts.py`, `brief_parser`, `source_watch` (P3), plus newer
`lane-b` commits (silence trim off by default, research doc). Each is merged when its phase starts.
