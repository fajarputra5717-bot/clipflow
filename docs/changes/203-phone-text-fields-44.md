# 203 · Phone text fields ≥ 44 px (deep audit M3, 2026-10-13)

Measured at 390 px, mocked pages, counting `::before`/`::after` hit areas and wrapping labels:
- Real failures, all in the Settings sheet: setting inputs `#set-*` 34 px tall, posting-time inputs and
  `#reminderLead` 36 px. Fix: the ≤ 600 px touch rule now gives every text-like `input` and `textarea` `min-height: 44px`
  (after: all 44 px).
- Already fine through their hit areas (182), so no change: `.ed-switch` 42×26 → 44×44, `.ed-sw-sm` 26×26 → 44×44,
  `.ai-switch` 51×31 → 53×45. The audit's "editor number input 40 px" was not found: editor.js has no number input and
  its one text field (hook title) is 46 px.
- `touch.spec` missed these because it never checked inputs/textareas or opened the sheets, and the fixtures gave
  Settings no fields. It now checks text inputs + textareas (checkboxes by their label), seeds settings, and walks the
  Settings + Watermarks sheets (it failed with 7 targets before the fix).
