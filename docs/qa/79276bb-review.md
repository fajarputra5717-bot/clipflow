# editor-compact 79276bb (224, Editor-only compact shell) — frames + touch targets + geometry

Served myself (frontend only): two throwaway nginx containers on the staging network with the staging nginx conf, one with `git archive origin/editor-compact` (v3.224) and one with main 081dd3a (v3.223) as the baseline, both proxying to the staging backend (removed afterwards). Measured as lane-c-a on the same clip, same Playwright run, headless software rendering (so only relative to main is meaningful).

## 1. Frames (rAF; slow = > 20 ms, worst in ms)
| segment | 1280×800 | 1280×700 | 1440×900 | 390×844 |
|---|---|---|---|---|
| scroll Review (16 wheel steps) | 0 / 17 (main 0) | 0 / 17 (0) | 0 / 17 (0) | 0 / 17 (0) |
| ENTER the Editor (dock → pill) | 0 / 17 (0) | 0 / 17 (0) | 0 / 17 (0) | 0 / 17 (0) |
| scroll in the Editor (12 steps) | 0 / 17 (0) | 0 / 17 (0) | 0 / 17 (0) | 0 / 17 (0) |
| LEAVE the Editor (pill → bar) | 0 / 17 (main 1 / 33) | 1 / 33 (0) | 2 / 33 (main 1 / 33) | 0 / 17 (0) |
| 4 page switches | 4 / 33 (main 3 / 33) | 0 / 17 (0) | 6 / 33 (6 / 33) | 0 / 17 (0) |
| re-enter + leave | 1 / 33 (1 / 33) | 0 / 17 (0) | 3 / 33 (2 / 33) | 0 / 17 (0) |
Result: no regression against main; 0 dropped frames on every scroll and on entering the Editor; leaving the Editor and page switches on desktop still show 1–6 frames at 33 ms (2 frames; 0 over 34 ms), same as main, as with phase 1 (software rendering; needs real hardware). Phones are clean everywhere. 0 page errors.

## 2. Touch targets in the Editor at 390×844
- OK: top-bar icon buttons 44×44 on phones (desktop 36–44 × 40, as the owner accepted); dock = `.is-pill` with 44×44 buttons (360×52); no horizontal overflow; the page scrolls as before.
- **Not OK (owner's ask: ≥ 44 px in the Editor at 390), same as main, i.e. not a regression:** the trim handles "Clip start" / "Clip end" are 18×142 px, the five keyword colour swatches 26×26, and the editor switches 42×26. My hit-test (probing 22 px around each control centre) shows their hit areas are NOT padded to 44 px (earlier reviews took the padded `::before` areas for granted; measured now they are not there). Everything else in the Editor at 390 measures ≥ 44 px. Suggested: `::before{inset:-9px}` on `.ed-sw`, `.ed-switch` and a wider hit area for `.ed-trim-h`.

## 3. Geometry at 1280×800, 1280×700, 1440×900, light + dark
- Top bar 44 px (main 56) directly under the staging banner (no other strip); dock pill 374×52, 44 px buttons (main 408×58, 48 px); other pages untouched.
- Video at the default split (staging, 22 px banner): 1280×800 252×448 (main 221×392; Lane A's 455 is without the banner), 1280×700 225×400 (main 194×344), 1440×900 256×455 (unchanged, capped); light and dark identical. No page scroll (scrollHeight = innerHeight) and no horizontal overflow at the six size/theme combinations; "Apply to all clips" does not overlap the presets at 1280×700.

## Findings
- **Medium (existing, now asked by the owner):** trim handles 18 px, swatches 26 px, switches 42×26 below 44 px at 390 in the Editor (above).
- Low: leaving the Editor and desktop page switches still drop 1–6 frames in software rendering (as main).

## Not verified
Real-hardware frames; Safari; the dock flip with a real touch scroll.

Merge: OK for 79276bb (compact shell works; frames equal main). The 44 px target gap is not caused by it but should be fixed before the owner's "≥ 44 px in the Editor" is claimed.
