# lane-b e82389e — inspector tabs scroll + keyword box (staging :8080)

Measured on my lane-c-a clip (32 keyword chips) with Playwright at 320×640, 360×740, 390×844, 768×1024, 1280×800.

## Tabs
- PASS: 0 labels clipped at all 5 sizes. 390/768/1280 fit with no scroll and no fade (row 376/736/380 px). 360 (row 346 vs content 354) and 320 (306 vs 354) scroll sideways with the right-edge fade (`more-end`); after selecting the last tab (Export) the row scrolls it into view (scrollLeft 8 at 360, 48 at 320), the selected tab is fully inside the row and the fade moves to the left edge (`more-start`). The click on the last tab through the fade works (fade does not eat clicks).
- Tab height 44 px on phone widths (≤ 390), 32 px at 768 and 1280 (tablet-size Low, as before).

## Keywords
- PASS at 390 / 360 / 320: `.ed-kw` is 192 px = 4 whole rows of 44 px chips, scrolls inside (overflow-y auto, content 242 px at 390, 290 at 360/320); the "Scroll the words for more ↓" line shows while words are below and hides once scrolled to the end. At 1280: 112 px (4 rows of 24 px), content 142 px, hint shown.
- **Low:** at 768×1024 the box is 56 px tall (2 rows) with content 58 px: only 2 px "hidden", yet the hint "Scroll the words for more ↓" is shown (and the box has the bottom fade). Needs a tolerance (e.g. scrollHeight > clientHeight + 4) or the 4-row height; harmless, just a false prompt.

## Not verified
The long-keyword-list path on lane-b-e1 clip 0782e50b (Lane B's data); keyboard arrow navigation between tabs; dark theme fade colour; real touch scrolling of the tab row.

Merge: OK
