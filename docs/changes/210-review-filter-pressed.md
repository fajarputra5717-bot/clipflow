# 210 · Review / Pick-a-clip status filter: pressed = accent too (Lane C Low on 205, 2026-10-14)

205 fixed the class-less `.seg` buttons, but Review's filter (`.rv-seg`, editor.css) has its own pressed style: a
`--panel` thumb, rgb(28,28,30) on the dark track (~1.2:1). It now uses the same `--seg-on` accent + white text
(light 4.7:1, dark 5.6:1), unpressed transparent on the track, hover `--fill2`, with dark-theme selectors so the generic
dark button rules can't win. touch.spec's 205 sweep now also checks `.rv-seg` (it failed on "To review" before).
