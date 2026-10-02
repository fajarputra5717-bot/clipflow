# 116 · Keyword colour defaults to one that contrasts with the caption style (follow-up to 111) · worker.py, shared/edit_spec.py, index.html

The default keyword yellow equals the karaoke highlight of the yellow styles (outline, bold, boxed, hormozi,
gold): keywords only stood out before the sweep. Now an UNSET keyword colour is resolved at render time by
`edit_spec.contrasting_keyword_color(style highlight)`: the first swatch (yellow, green, red, cyan, purple) at
least 120 RGB away from the highlight (outline/gold → green; neon/clean/impact → yellow). `keywords_of()`
returns None for an unset colour; a colour the user picked is always kept. The UI mirrors it (`kwAutoColor`:
the selected swatch and the preview follow the clip's style until a colour is picked; Apply doesn't save the
auto colour).

**Verified:** IME clip 1a9833d4 (outline style, AI keywords, no colour) re-rendered → keyword tags
`\1c&H0058D130` (green) while the style highlight stays yellow `&H000AD6FF`; harness 34/34.
