# lane-b 65f8aef (editor sound) + 44e7847 (page fits the window) — staging :8080 (lane-b, main 917b765 + these)

Tested with my own lane-c-a clip (preview with audio), Playwright at 6 sizes + 1280 screenshot.

## 65f8aef — preview sound (closes the audit High)
- PASS: speaker button `[data-ed-mute]` is there (44×44), starts muted with label "Unmute", click → unmuted (muted=false, volume 1, label "Mute"), choice survives a tab re-render (Captions → Audio), and playing unmuted decodes audio (webkitAudioDecodedByteCount 95,902). Hit-testing on the button centre returns the button at every size.
- PASS: the Audio tab states that compression, Loud & punchy, loudness and effect sounds are heard after Render preview (honest: the preview is not live-processed).
- Not verified: actual audibility on a device (headless), the remembered volume (fix 2), that mute persists across leaving and re-opening the editor (not claimed).

## 44e7847 — desktop layout
- PASS: at 1280×800, 1440×900 and 1024×768 `scrollHeight == innerHeight` (no page scroll); video left, play/time/mute row under it and hit-testable, "Preview is up to date / Render preview" bar beside it (no longer over the video); inspector scrolls inside (`.ed-panel` 1019 > 326 px); timeline docked full width, bottom 8–21 px above the stepper pill (no overlap); leaving the editor restores body padding (72 px) and the normal page height.
- PASS: windows under 768 px tall (1280×700), narrower than 900 px (800×900) and the phone (390×844) keep the scrolling layout; phone order video (sticky) → timeline → inspector; mute/play 44×44.
- Trade-off you asked me to judge: the video is only 169×300 at 1280×800 (225×400 at 1440×900, 151×268 at 1024×768) in a ~800 px empty left column; captions are hard to judge at that size, and the editor's whole job is judging captions. Medium (design), not a blocker. Cheaper ideas: shrink the timeline (waveform 142 px → ~100 px or collapse the word row), put the timeline under the inspector instead of full width, or let the video column be as tall as the inspector and scale the player to the free area.
- Low: in the short window (1280×700) the mute button's bottom 16 px sits under the pill at the initial scroll (known: sticky bar covers controls in the scrolling layout, Lane B's fix 2).
- 0 page errors in all 6 sizes.

## Not verified
Real touch use of the new phone order, other themes (dark), the new editor.spec in my run (Lane B ran 258 passed), a render after layout changes (no render code touched).

Merge: OK (65f8aef and 44e7847; the video size is a design decision for the owner).
