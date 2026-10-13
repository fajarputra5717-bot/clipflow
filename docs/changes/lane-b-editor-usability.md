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
3. Player (owner fix 2): sound on by default; mute + volume remembered per browser (`localStorage`
   `clipflow.editor.sound`, try/catch, re-read on open). If the browser refuses autoplay with sound, it plays muted and
   the speaker shows it (not saved). Row under the video: play · time · scrub bar (transform-only) · mute · volume
   (volume hidden ≤ 600 px: phones ignore it). Keys (`playerKey()`): Space/K play-pause, ←/→ 0.1 s, Shift 1 s, J back
   1 s, L play then 1.5×/2× (browsers can't play in reverse), M mute; never in text fields/selects/sliders or outside
   the editor; Space still activates a focused button/switch/tab. Short desktop windows: the sticky player ends above
   the sticky action bar. UI tests serve a 4 s WebM (`tests/ui/media/clip-4s.webm`) with byte ranges.
4. Inspector (owner fix 3): the tab row is a sideways scroller (labels never ellipsize; 8–10 px padding) with a fade at
   the hidden edge (`fadeEdges()`, classes `more-start`/`more-end`); keyword words show 4 whole rows (24 px chips
   desktop, 44 px phone) and scroll inside their section, fading at the bottom with "Scroll the words for more ↓"
   (`#edKwMore`) while words are hidden below (4 px tolerance: chip tap areas overhang the box, QA e82389e Low).
5. Smooth motion (owner fix 4): playhead, scrub bar and progress move by transform only. Per-frame painters write the
   DOM only when a value changes (`txt()`); layout reads come before writes, and the timeline width is cached
   (`E.tlW`). Dragging on the timeline's ruler/waveform (seek mode, not on a chip, handle or marker) now scrubs once
   per frame from a rect read at pointerdown. The waveform was already a canvas (`drawWave()`). Measured live at
   1280×800: 3 s of playback 378 → 32 layouts (67 → 7 ms); the 32 left are the time readouts' text, ≈ 0.2 ms each.
