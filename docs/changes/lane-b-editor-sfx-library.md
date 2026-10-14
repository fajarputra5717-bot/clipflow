# lane-b: Editor uses the SFX library (after 217)

The Effects tab reads Lane A's `GET /api/sfx` (on open and when the tab is selected; again when focus comes back
after "Your sounds" opened Settings → Sound effects). Each plan item's sound picker names what will actually play:
`Boom · My boom` for a category with the user's own sound, `Laugh (Ding until you add yours)` for laugh without one.
▶ next to the picker previews that exact file (own: `mediaUrl(/api/sfx/{id}/file)`; built-in: `/sfx/<name>.wav`,
laugh → ding) at the player's volume. "Your sounds" is a `data-open-sfx` button (the shell's handler opens the sheet).
`SFX_NAME` gains laugh; the three editor mocks list it.
