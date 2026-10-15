# 224 — Editor only: slimmer top bar + compact dock, so the video reaches 455 px at 1280×800

Owner 2026-10-15 (after 222's ×1.2 scale the default video was 414 px tall at 1280×800, below the 455 px target).
`body.editor-open` (editor.js) sets, in index.html's shell CSS: top bar 44 px (`--appbar-h`, `--ed-top`; desktop icon
buttons 40 px, phones keep 44), no strip above the bar, 8 px under it; the dock stays its compact pill (`.is-pill`
forced by initToolbar's apply(), which now also follows body.editor-open via a MutationObserver): 44 px buttons
(same tap targets, no shrink), 4 px padding, 8 px from the bottom. Every other page keeps 56 px / 48 px / the bar state.

| | before (main) | after |
|---|---|---|
| 1280×800 video | 414 px | 455 px (the default split's target) |
| 1280×700 video | 366 px | 422 px |
| 1440×900 video | 455 px | 455 px |
| top bar / dock in the Editor | 56 / 58 px | 44 / 52 px |

tests/ui/specs/editor-compact.spec.js (≥ 455 at 1280×800 and 1440×900, pill + 44 px targets, no page scroll, normal
sizes back on Schedule). Screenshots: /opt/clipflow/docs/ui-recordings/editor-compact/{before,after} (EDC_SHOTS).
