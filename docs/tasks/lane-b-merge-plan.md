# Lane-b → production merge plan (prepared 2026-10-07; execute ONLY after Lane C says "MERGE OK")

Owner 2026-10-06: when Lane C approves lane-b's Review page (9089c71) and editor tasks 1–4, merge lane-b to
production, switch Review/Editor navigation to the new pages and remove the old drawer.

## What comes in (origin/lane-b vs main, 38 files, +4 025/−24)
- **Review page** `frontend/html/editor/review.js` (#review, #review/<job>; flow-preview step 4) — 9089c71.
- **Editor page** `frontend/html/editor/editor.js|css` (#editor/<job>/<clip>; step 5): task 1 hook title card +
  shell (a67d58c), task 2 timeline (334a3ce), task 3 cuts (3597000), task 4 (not on lane-b yet: confirm the commit
  in Lane C's MERGE OK). Owner scoping fix d19b286.
- **Backend** `backend/app/routes_editor.py` (owner-scoped routes under /api/jobs/{jid}/candidates/{cid}/editor…),
  `/api/env` (staging banner). **Worker** `worker/render_steps.py` (title card, cuts, timeline peaks) + Dockerfile COPY.
- **Shared** `brief_parser.py` (P3), `timeline.py`, `edit_spec` keys `hook_title` / `cuts`, `retention` (silence
  trim off by default), `rule_checks` editor checks; tests (unit + editor/review UI specs); `docs/research/
  publishing-apis.md`; staging tooling (`docker-compose.staging.yml`, `scripts/staging.sh`, `docs/staging.md`).
- **No DB schema change** (only new `edit_spec` JSON keys) → rollback needs no migration.

## What switches
1. Stepper "Review" + tab bar "Review" (`data-nav="queue"`) → open `#review` (review.js) instead of the old queue
   list/detail; the job picker replaces the list.
2. Stepper "Editor" (`data-flow-editor`) → `#editor/<job>/<clip>` of the selected clip (disabled until a clip is
   picked, as now); "Open editor" on clip cards stays.
3. The "lane-b hook" one-liners in index.html / main.py / worker.py become normal code (no "hook" comments).
4. Lane-b change docs get numbers at merge (144+ in order: payouts already 131; brief parser, P4-1, P4-2, P4-3,
   P4-6 review, task 4) and INDEX lines; CLAUDE.md gains the Review/Editor page invariants.

## What is removed
- The old edit drawer in index.html: markup, `toggleCandidateEdit`, `switchEditTab`/`EDIT_TABS`, `editTab`,
  `editMoreOpen`, drawer CSS, `.edit-actions`, drawer-only listeners — **only for features that have a home in the
  new pages**. Parity table, filled in at merge (any "missing" row blocks removal of that piece; ask the owner):

| Drawer feature (data-*) | New home | Status at merge |
|---|---|---|
| Caption style / font / size / animation, presets (`data-preset`, `data-preset-all`) | Editor · Captions | verify |
| Keywords + colour, caption position | Editor · Captions | verify |
| Subtitle text edit + "Fix typos" AI (`data-fix-subtitle`) | Editor · Captions / timeline | verify |
| Hook title card, cuts, timeline | Editor (tasks 1–3) | new |
| Per-clip watermark, Effects/Audio/Export tabs | Editor tabs | verify |
| Thumbnails: AI options, upload, pick (`data-gen-thumbs`, `data-upload-thumb`, `data-pick-thumb`) | Editor · Export? | verify |
| Description + generate (`data-gen-desc`), rule fixes (`data-rule-fix`) | Review card / Editor | verify |
| Get another hook (`data-hook`) | Review card | verify |
| Versions + restore (`data-versions-toggle`, `data-restore-version`) | Editor | verify |
| Submagic start/export/use (`data-submagic-*`) | Editor · Export | verify |
| Approve (`data-approve`) + rule gate (409) | Review card | present (9089c71) |
| Apply / Render preview, Final render | Editor footer / Review | verify |

## Steps (Lane A)
1. `git fetch`; on main tag `pre-laneb-merge`; push the tag.
2. `git merge --no-ff origin/lane-b` (no squash: keeps Lane B history). Resolve conflicts (index.html, main.py,
   worker.py, CLAUDE.md, docs/changes/INDEX.md); main's versions of shared files win where lane-b only merged main.
3. Commits after the merge (small, each tested): (a) navigation switch, (b) hook one-liners → normal code,
   (c) drawer removal for every parity row marked present, (d) docs numbering + CLAUDE.md.
4. Tests: all unit tests (`python3 -m unittest discover tests`), UI harness (desktop + mobile; editor/review specs
   included); `python3 scripts/check_caption_mirror.py`.
5. Deploy (nothing running; import-test backend + worker images; `up -d backend worker`, health-gated by 143;
   frontend is a bind mount, hard refresh).
6. Verify on prod read-only: Review lists jobs, opening a clip's editor loads timeline/cuts; existing clips render
   identically (no hook_title/cuts keys = no change); then a staging write pass (lane-a-* users): edit → render
   preview → final, cuts + title card in the final, loudness −14 LUFS.
7. Tell Lane C (post-merge check) and Lane B (lane-b rebases on main; hook comments gone).

## Rollback
- Code: `git revert -m 1 <merge-sha>` plus the follow-up commits (or `git checkout pre-laneb-merge -- .` on a
  rollback branch), push, rebuild + import-test backend/worker, `up -d backend worker` (health-gated); frontend
  is live on save (hard refresh).
- Data: none to undo. `edit_spec.hook_title` / `cuts` saved meanwhile stay in the rows; pre-merge code ignores them
  (renders without title card/cuts); previews/finals already rendered keep their files.
- Decision rule: any High from Lane C's post-merge check or a broken render → rollback first, fix on lane-b, re-merge.
