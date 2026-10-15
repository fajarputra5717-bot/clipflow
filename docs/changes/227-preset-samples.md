# 227 — preset samples never clip (Lane C Low/Medium after the ×1.2 scale, 222)

On phones the preset tile is 101–111 px wide and the "THIS CHANGES" sample (14 px Montserrat Black) clipped (390: 1 of
6 tiles, 360: all 6). The tile is now an inline-size container and the sample is `min(var(--fs-small), 11cqi)`:
full size where it fits (desktop unchanged), smaller only in narrow tiles. editor.spec checks 360 and 390 px.
