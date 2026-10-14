# lane-b aa9aee0 (editor ↔ SFX library) + d013824 (split timeline fits its row) — staging :8080 (lane-b on main 993a1b2)

## d013824 — PASS (fixes my design note, a real bug in 4ab7884)
Default split (localStorage cleared), lane-c-a clip: timeline box bottom vs pill top: 1280×800 730 < 742, 1440×900 830 < 842, 1280×700 630 < 642, 1280×640 570 < 582, 1024×768 698 < 710 (was ~850 vs 742); the box (`.ed-tl`, 72 px; 151 px at 1440) scrolls inside (content 190 > 70 / 210 > 149) so the word chips are reachable by scrolling; page scrollHeight = innerHeight everywhere. `scrollIntoView` on the last word chip no longer moves the grid (0 px shift, document scrollTop 0, chip visible inside the box); the page is `overflow: clip`. 0 page errors.

## aa9aee0 — PASS
- Effects tab fetches `GET /api/sfx` on open and again on every tab re-select.
- The pickers name what will play: with my boom sound assigned "Boom · My boom"; unassigned laugh "Laugh (Ding until you add yours)"; plain "No sound" / Whoosh / Bass hit / Ding / Record scratch for the rest. The selected value follows each plan item (boom item shows "Boom · My boom").
- ▶ plays the exact file: the own sound requests `GET /api/sfx/<id>/file?mt=…` (200), the laugh fallback requests `GET /sfx/ding.wav`.
- "Your sounds" (`data-open-sfx`) opens Settings → Sound effects; closing the sheet re-reads `/api/sfx` (the Effects tab refreshes when focus returns).
- Low: closing the sheet issues two `GET /api/sfx` (one from the sheet, one from the editor); harmless.

## Not verified
That ▶ plays at the player volume (headless), pickers on phone width, a render after choosing a sound from the new picker (the render path was checked in cd82e80), keyboard use of the pickers.

Merge: OK for aa9aee0 and d013824.
