# lane-b: Editor usability (audit High + owner's four fixes, 2026-10-14)

1. Preview sound (audit High): speaker button under the video (`data-ed-mute`, `setMuted()`); muted by default
   because the preview autoplays, the choice holds while the page is open. Audio edits are baked into the preview
   render (silence trim, compression, Loud & punchy, loudnorm, SFX all run in `create_preview`), so the Audio tab
   says they are heard after Render preview (`#edAudioNote`) instead of faking them live.
2. Layout (owner fix 1): desktop ≥ 900 × 768 = no page scroll. `.ed-page.ed-fit` is a grid (head / video + inspector /
   player controls + action bar under the video / timeline docked full width); `.ed-grid`/`.ed-player` are
   `display:contents`. Height `--ed-fit-h` = window minus the page top and the stepper pill (`fitPage()`, on render +
   resize). The inspector panel scrolls inside. Shorter or narrower windows keep the scrolling layout. Phone (≤ 899):
   video (sticky), timeline right under it, then the inspector tabs, via flex `order`.
