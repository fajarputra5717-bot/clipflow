# lane-b 434f6bc — editor player (sound on, remembered volume, scrub bar, keyboard) — staging :8080

(Lane B's first message named it 2f4c3b5, corrected to 434f6bc.) Tested on my lane-c-a clip with Playwright: autoplay allowed, autoplay blocked, 1280×800, 1280×700/640/768, 390.

## Verified
- Default: sound ON (muted=false, volume 1) with nothing saved in localStorage until the user acts. With autoplay blocked (default Chromium) the preview plays MUTED and the speaker reads "Unmute"; nothing saved.
- Row under the video: play 44×44, time, scrub 282×28 (219×44 on phone), mute 44×44, volume 84×40; volume slider hidden (display none) at 390; all clickable at 1280×700/640/768 and 390 (hit-test returns the control), none under the action bar or the pill at scroll 0 or 400. The sticky player now ends above the "Render preview" bar (controls 496–540 vs button 581 at 700 tall; 446–490 vs 521 at 640): your Low is closed.
- Keys (focus in the editor, not in a field): → +0.1 s, ⇧→ +1 s, ← −0.1 s, J −1 s, Space plays, K pauses, L plays, L again 1.5×, again 2×, M mutes/unmutes. All measured via `currentTime`/`playbackRate`/`muted`.
- Guards: typing " k m l j " in the caption text area does nothing to the video; ArrowLeft on the volume slider changes volume only (1 → 0.95, time unchanged); Space on a focused tab activates the tab (Audio) and does not play.
- Scrub: click at 50% → 16.91 s of 33.8 s; fill is `transform: scaleX(0.5)`, thumb `translateX(50%)` (transform only).
- Persistence: `clipflow.editor.sound` = {"muted":false,"volume":0.4} after changing volume; after reload volume 0.4, sound on. 0 page errors.

## Findings (Low)
- Moving the volume slider while muted also unmutes (the saved state shows muted:false). Usual behaviour, but say so in the label/tooltip if intended.

## Not verified
Real audibility; iOS/Safari behaviour (volume ignored there, as you noted); keys when focus is outside the editor page (I only tested inside); the 4 s WebM fixture test (Lane B: 260 passed).

Merge: OK
