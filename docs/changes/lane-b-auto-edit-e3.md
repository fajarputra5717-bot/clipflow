# Auto Edit E3 — emoji pops + SFX (lane-b)

- Emoji: PNG overlays (libass can't draw colour emoji) from `worker/assets/emoji/` = Twemoji 15.1.0 graphics,
  **CC-BY 4.0** (credit: "Emoji graphics by Twemoji, licensed under CC-BY 4.0", © Twitter, Inc and other
  contributors), rendered from SVG to 256 px. 8 bundled: 😂😭💀🔥😱👀🤯😎. `retention.emoji_filters`: pop (115 % → 100 %),
  1.4 s, alpha fade; zoom stage AFTER the motion (emoji don't zoom/shake) and BEFORE watermark + captions (they are
  drawn on top: never covered), at 42 % height, alternating right/left.
- SFX: `worker/assets/sfx/` whoosh, boom, bass_hit, ding, record_scratch — generated in-house by `scripts/make_sfx.sh`
  (ffmpeg synthesis, no samples), released **CC0**. A laugh needs a real CC0 recording (not bundled; not offered).
  `render_steps.mix_sfx` after the cut stage, before loudness: each item's `params.sfx` at its OUTPUT time (through
  cuts + freeze/slow-mo), SFX bus side-chain ducked by the speech; loudnorm stays last.
- `worker/assets/LICENSES.md` lists every bundled file (incl. watermark.png = Motion Klip, not redistributed); a unit
  test fails if an emoji/SFX file or its licence row is missing.
- Editor: per plan item a Sound picker, and an emoji picker on emoji items. `director.sfx` / `director.emoji` lists.
- Verified on staging (lane-b-e1 clip 2a497ffb, cut 10–11 s, 5 items with sounds): logs "Emoji: 2 pop(s)", "SFX: 5
  mixed under the speech", preview + final 30.2 s, final -13.7 LUFS / -2.7 dBTP. Frames: 😂 right / 💀 left between the
  watermark and the captions, whip across the seam, captions + watermark intact. Sounds present: low band +6.5 dB at
  the boom, +21.7 dB at the ding's pitch vs just before. Unit: tests/test_overlays_sfx.py (6).
