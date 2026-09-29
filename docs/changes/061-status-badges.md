# 061 — Status badges: semantic colours, AA contrast in both themes (TASKS-UI-QA T6)
Date: 2026-09-29 · Commit: see `git log --grep "UI-QA T6"` · Files: frontend/html/index.html · UI v2.1106

## What changed
- `badgeClass()` has six classes instead of five: **idle** grey (`queued`, every `*_queued`), **running** blue
  (active work and unknown states), **attention** amber (`review`, and `partial_failure`, which used to be blue),
  **completed** green, **failed** red, **cancelled** (grey text and outline, no fill).
- Colours are `--badge-{idle,run,warn,good,bad}-{fg,bg,line}` tokens in `:root` and `:root[data-theme="dark"]`. The
  dark theme now has its own lighter text colours. Before, it reused the light-theme text on a dark tint.
- Running badges get an indeterminate shimmer (`::after`, behind the text, 1.8 s linear). It is hidden under
  `prefers-reduced-motion`.
- Labels: "Thumbnail queue" → "Thumbnail queued". Unknown states print humanised ("Weird new state"), not the raw enum.
- `stageColor()` (rings and mini bars) follows the new classes.

## Why
ui-audit.md §3: the badges failed WCAG AA, queued looked the same as running, and partial failure read as "in progress".

## Measurements (headless Chromium, computed styles, fill composited over the real card background)
Before: **8 of 10 fail**. The audit listed 7; light "running" is 4.21, not a pass.
Light: running 4.21, review 3.53, completed 3.77, failed 4.77, cancelled 4.57.
Dark: 3.39 / 3.76 / 3.54 / 2.91 / 2.95.
After: all pass (worst case with the shimmer peak composited), the same in `.job-card`, `.job-card.processing` and
`.candidate-card`.
| | idle | running | attention | completed | failed | cancelled |
|---|---|---|---|---|---|---|
| light | 6.55 | 6.14 | 6.01 | 5.57 | 6.37 | 7.54 |
| dark | 6.24 | 5.06 | 5.80 | 5.81 | 5.05 | 8.29 |

## Decisions & trade-offs
- Queued and cancelled share the grey hue because neither needs action. They differ by fill (tinted vs outline only).
- A missing or unknown status stays blue: the job path defaults it to "processing", and blue is safer than implying "idle".
- `.tag` (job detail header) is unchanged. It is neutral text on a neutral chip.

## Gotchas for future changes
- New status → add it to `stageLabel()` and check that `badgeClass()` buckets it correctly (`*_queued` is automatic).
- Changing a `--badge-*` value: re-measure in both themes against `--panel`. The dark failed pair has the least margin (5.05).
