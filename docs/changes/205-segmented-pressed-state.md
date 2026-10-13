# 205 · Segmented buttons: pressed state follows aria-pressed in both themes (owner bug, 2026-10-14)

Dark theme showed every segmented control inverted (Language, Game : cam, Cam position, Output platform, Clips): the
pressed option grey, the others blue. Cause: the dark "primary button" rule `[data-theme="dark"] button:not([class])
:not([role])` (specificity 0,3,1) painted every class-less button accent blue, and the segment buttons have no class,
so it outranked `[data-theme="dark"] .seg button` (0,2,1); the pressed rule (0,3,1, later) still won for the pressed one
and drew the old grey thumb (`--seg-thumb` #636366). The JS was right (aria-pressed + .active on the right button).
Fix: primary-button rules exclude `[aria-pressed]` (a toggle is never a primary action); `.seg` pressed =
`--seg-on` + white text (light #0071e3 = 4.7:1, dark #0066cc = 5.6:1, dark's #0a84ff accent would be 3.65:1);
unpressed = transparent on the neutral track; hover on unpressed = `--fill2` (lighter grey), no shadow. Light theme
moves from the white thumb to the same accent so both themes read the same.
Spec: touch.spec "205: toggles follow aria-pressed" (dark + light, desktop + phone) walks all 8 steps, the 6 Editor tabs
and the Settings/Watermarks sheets: no unpressed toggle may be accent blue; pressed `.seg` buttons must be accent with
text ≥ 4.5:1. It failed on the old CSS in dark with 9 pressed-grey + 17 unpressed-blue toggles: Analyze (Language, Game : cam, Cam
position, Output platform, Clips) and also the Review / Pick-a-clip status filter, Schedule's List/Week switch and the
Publish filter (same class-less `.seg` buttons). UI 243 passed.
