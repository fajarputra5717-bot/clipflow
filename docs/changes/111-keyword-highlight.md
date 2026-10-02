# 111 · Keyword highlight: AI-picked, stoplist-filtered, tap to toggle, colour choice, baked into the ASS (P1 editor commit 5) · worker.py, shared/edit_spec.py, index.html, tests/ui

**Now.**
- `edit_spec.keywords` (normalised tokens, max 20; an explicit `[]` = none) and `edit_spec.keyword_color`
  (`#RRGGBB`, default `#FFD60A`), validated in `shared/edit_spec.py`.
- Worker `pick_keywords()`: at preview build, before the ASS is written, one utility-model call (`task=
  "keywords"`) per clip picks 3–6 hook words; kept only if really in the clip, ≥ 3 letters and not on the
  job language's stoplist (`shared/languages.stopwords_for`). Skipped when the clip already has the key
  (user toggles and an explicit `[]` are never overwritten). Never fatal.
- `make_ass(…, keywords, keyword_color)`: every mode (karaoke `\kf`, word pop / bounce / fade chunks,
  typewriter, static) draws keyword words with `\1c` + `\2c` = the keyword colour (a karaoke sweep can't
  recolour them), then resets to the style's own highlight / resting colours. Preview and final both pass the
  clip's keywords.
- UI (Captions tab, under the live preview): colour swatches (yellow, green, red, cyan, purple, as the mockup)
  and a strip of every caption word: tap to toggle; the animated preview colours keywords live. Apply sends
  `keywords` / `keyword_color` only when the user changed them.
- Test: `keywords.spec.js` (toggle → preview `.kw`, green → Apply sends both).
- Note: the default yellow equals the karaoke highlight of the yellow styles, so there a keyword stands out
  only before the sweep reaches it; pick another colour for those.

**Verified** on the stack: Windah clip fddd5fab → AI picked [hantu, sumpah, takut, lukisan, mati] (Gemini),
ASS carries the keyword tags with resets; manual [takut, lukisan] in green → frame at 30.3 s
shows LUKISAN green while the karaoke sweep (yellow) is still on "LU A"; harness 30/30.
