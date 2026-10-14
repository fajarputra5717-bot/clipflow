# 218 — Editor video/timeline split (owner 2026-10-14, after 215/216)

Owner picked option (b): the timeline stays full width, with a draggable line (`.ed-split`, `role=separator`) between
the video and the timeline. The two rows share a fixed height, so `--ed-tl-h` (timeline height) sets both.
- Default: a 455 px tall video where it fits (timeline = space − 455, never under 72 px = buttons + ruler + a waveform
  strip; the hint line hides below 140 px via a container query). Video keeps ≥ 200 px.
- Drag (pointer, once per frame) or keys on the focused line: ↑/↓ 16 px, Shift 64 px, Home/End = biggest/smallest
  timeline; `aria-valuenow` = video share in %, `aria-valuetext` = both heights.
- Remembered per user in this browser (`lsSet("editor_split")`, the shell's per-user localStorage key).
- The no-scroll layout now starts at 640 px tall (was 768); 640–767 px tall also moves the title row above the
  inspector so the video starts at the top.
Measured on staging (22 px banner; production gets +22 px): 1280×700 188×334 → 210×374 (and no page scroll),
1280×800 169×300 → 244×434, 1440×900 225×400 → 256×455.

## Word chips: one Tab stop (owner 2026-10-14, separate commit)
The timeline's word + pause chips are one roving-tabindex group (`setRoving()`, `chipKey()`): one Tab stop, ←/→ move
in time order, Home/End jump to first/last, Enter/Space act as before; a clicked chip becomes the stop and keeps it
across repaints (`E.rove`). Measured from the play button at 1280×800: first inspector tab 97th → 21st, Render
preview 152nd → 76th (the inspector's keyword chips are still one stop each).
