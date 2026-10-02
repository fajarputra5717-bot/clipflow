# QA review · 83e35d4 · 078 watermark 16 % floor + pilot campaign fixtures

Reviewer: Lane C · 2026-10-02 · reviewed against committed HEAD

Invariants checked: placement still only in `get_watermark_rect()`; all three consumers go through
it (`make_ass` push-up `worker.py:3603/3628`, Submagic `apply_watermark_overlay` `:3964`, burn-off
render `:4160`), so the floor applies with subtitles off and to Submagic output too (OK).
`resolve_watermark_path`, `thumbnail_locked`, layout threading: untouched.
Live output: all 3 finals have the mark at y ≈ 21–28 % (frames in `clips-2026-10-02.md`), inside
the 15.9–83.9 % safe band.

## Findings (most severe first)

1. **Low · Settings still allow 5 %.** `percent_setting("WATERMARK_POSITION_Y", 25.0, 5, 95)`
   (`backend/app/main.py:824`) and the Settings field accept 5–15 %, which the worker now silently
   clamps to 16 %. Settings UI should show min 16 or warn.
2. **Low · overlap is possible by design.** With very tall captions the mark stays at 16 % and
   overlaps the caption band (WARNING log only, no UI surfacing). Acceptable per change doc; worth a
   job-level warning later.
3. **Process** · commit subject lacks the `feat(R-NN)`/scope form; numbering committed out of order
   (079 before 078).

## Campaign fixtures (docs only)
Rules JSON parse not executed by QA; they're consumed by uncommitted 081 (`shared/campaigns.py`),
which will be reviewed when it lands on main. Open items in the change doc (budget, rounding,
per-account limits) are business TBDs, not bugs.

## Not verified
- 540×960 preview path visually (only finals checked).
- The "400 px captions → y=307 + warning" case (change-doc claim, not reproduced by QA).
