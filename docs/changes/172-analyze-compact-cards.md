# 172 · Analyze job cards = compact Review-style cards (shell item 5, 2026-10-09)

- `createJobCard()` / `patchJobCard()` (still keyed + patched in place, 074): thumbnail (first clip's, else the
  YouTube frame) · title (rename) · status chip · campaign · date · mini island while running · Cancel/Retry. A
  stretched link makes the whole card open `#review/<job>`; buttons sit above it.
- Removed the old copy ("Tap a job to review both candidates side by side", "Click anywhere to review this job") and
  the split/format/Details lines; the classic queue cards show the date instead.
- jobs.spec: compact card test. 182 passed. Screenshots: docs/ui-recordings/shell-v2/after/*-3-analyze-cards.png.
