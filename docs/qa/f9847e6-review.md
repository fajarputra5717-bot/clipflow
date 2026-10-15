# lane-b f9847e6 + 20623d1 (trim-handle hit areas) — staging (lane-b, restaged bfb184c = main 92b58d3 + fix)

## Verified (390 and 360 px, light, lane-c-a clip; video paused first, because the playhead follow-scroll fights a manual scroll)
- **Trim handles, real hit extent** (elementFromPoint scanned outward from the handle centre in 0.25 px steps, handle placed at y ≈ 510, clear of the sticky player and the dock): **Clip start 44.5 px wide (22.8 left / 21.8 right), Clip end 44.5 px wide**, in both Seek and Cut mode, with the scroller at 0 (handle at the clip start, formerly clipped to 23 px), at its end, and with the handle centred; same at 360. Matches Lane B's 45 px. No horizontal overflow, 0 page errors.
- **Timeline behaviour unchanged by the 24 px inset:** at 1280×800 and 390×844 a click on the ruler 200 px from the inner's left seeks to 2.00 s and a drag from +100 to +460 px scrubs to 4.60 s (exact, 100 px/s).

## Findings
- Low/Medium (Lane B already knows): keyword preset samples clip their "THIS CHANGES" text on phones: at 390 the 6th tile (tile 111 px in a 121 px button) and at 360 all six tiles (101 in 111); 430 fits. From the ×1.2 scale, not this fix.
- Note for future probes: a first scan with the video playing read 0 px because the follow-scroll kept moving the scroller (the handle was off-screen); pausing fixes it.

Merge: OK for f9847e6 and 20623d1 (the last open Editor touch-target item is closed).
