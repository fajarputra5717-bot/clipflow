# 207 · Phone sliders ≥ 44 px (deep audit M3 follow-up, 2026-10-14)

Lane C named the "editor number input 40 px": it was the range sliders. At 390 px five editor sliders were 210×40
(Caption size, Caption position, Zoom intensity, Watermark width, Watermark opacity). The ≤ 600 px touch rule from 203
now covers `input[type=range]` too (native sliders, no custom track: the taller box only adds hit area); touch.spec
checks sliders (it listed those five before the fix). Editor files unchanged (Lane B told).
