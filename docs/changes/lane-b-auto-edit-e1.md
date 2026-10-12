# Auto Edit E1 — edit plan (lane-b)

Spec: docs/tasks/auto-edit.md. `shared/edit_director.py` (pure) builds a per-clip plan from the preview's
timeline cache: utility-AI moments (hook/punchline/shock/laugh, router task `edit_moments`), vision reactions
from 6 frames sampled at preview render (`previews/<cid>.frame-N.jpg`, source time, listed in the timeline cache
as `frames`), loudness peaks from the cached waveform, cut seams. Restraint: ≥ 3 s apart, not under the hook
title card, not in cuts/trim, not in the last 0.5 s, ≤ 12 items. Stored in `edit_spec.director`
(`normalize_director`), API `POST/PUT …/editor/plan` (owner-scoped, 1 attempt per provider; a vision failure
retries text-only). UI: Effects tab "Auto edit" list + timeline plan lane, each item toggleable.
Rendering today: only `punch` (merged into the zoom stage with the manual markers); shake/whip/emoji are
planned and labelled "arrives in E2/E3".

Invariants to fold into CLAUDE.md (AI calls): `ai_generate_json(..., images=[jpeg bytes])` sends images
(Gemini parts / Claude image blocks); setting `EDIT_DIRECTOR_VISION` (default true).

Verified on staging (lane-b-e1, job 96952037): plan in 9 s with frames (Gemini 503 → Claude Haiku failover),
6 items; preview render log "Zoom: 4 punch-in(s) (4 from the edit plan)"; toggle PUT, cross-user 404, bad
item 400. Unit: tests/test_edit_director.py (9). UI: editor.spec "Editor Auto edit plan"; director key added
to the touch/shots editor mocks.
