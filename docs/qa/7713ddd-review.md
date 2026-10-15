# lane-b 7713ddd (preset samples no longer clip on phones) — staging (lane-b frontend, merged with main 9033424)

Measured as lane-c-a on the Editor Captions tab: for each of the 6 preset tiles the sample text's range width vs its tile (clipped = text wider than the tile or the sample box outside it).

| width | tile | sample font | tiles clipped |
|---|---|---|---|
| 320 | 88 px | 9.7 px | **1 of 6** (text 1.02 × the tile) |
| 360 | 101 px | 11.1 px | 0 of 6 (was 6/6) |
| 390 | 111 px | 12.2 px | 0 of 6 (was 1/6) |
| 430 | 125 px | 13.7 px | 0 of 6 |
| 768 | 229 px | 14 px | 0 of 6 |
| 1280 / 1440 | 136 px | 14 px (unchanged) | 0 of 6 |

No horizontal overflow and 0 page errors at any width. Visually at 360 the three visible tiles show "THIS CHANGES" whole and sharp inside their dark pills.

Findings: Low only: at 320 px (below the usual phone minimum) one tile still clips and the sample drops to 9.7 px.

Merge: OK for 7713ddd.
