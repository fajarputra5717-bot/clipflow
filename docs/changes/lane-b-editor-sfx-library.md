# lane-b: Editor uses the SFX library (after 217)

The Effects tab reads Lane A's `GET /api/sfx` (on open and when the tab is selected; again when focus comes back
after "Your sounds" opened Settings → Sound effects). Each plan item's sound picker names what will actually play:
`Boom · My boom` for a category with the user's own sound, `Laugh (Ding until you add yours)` for laugh without one.
▶ next to the picker previews that exact file (own: `mediaUrl(/api/sfx/{id}/file)`; built-in: `/sfx/<name>.wav`,
laugh → ding) at the player's volume. "Your sounds" is a `data-open-sfx` button (the shell's handler opens the sheet).
`SFX_NAME` gains laugh; the three editor mocks list it.

## Split fix (follows 218 / 4ab7884)
The timeline box (`.ed-tl`) had `height:100%` inside `<details>`, which doesn't resolve: at the default split it ran
~120 px past its row (under the stepper, off the window) and never scrolled, so the words were only reachable by
dragging the line. It now takes `--ed-tl-h` directly and scrolls inside. The fit page is `overflow:clip` (was
hidden): script, focus or find-in-page could scroll the page grid and shift the whole layout up (measured 78 px).
